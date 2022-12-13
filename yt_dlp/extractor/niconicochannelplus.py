import functools
import json

from .common import InfoExtractor
from ..utils import (
    ExtractorError,
    OnDemandPagedList,
    UserNotLive,
    filter_dict,
    int_or_none,
    parse_iso8601,
    parse_qs,
    traverse_obj,
)


class NiconicoChannelPlusBaseIE(InfoExtractor):
    _WEBPAGE_BASE_URL = 'https://nicochannel.jp'

    def _call_api(self, path, item_id, *args, **kwargs):
        return self._download_json(
            f'https://nfc-api.nicochannel.jp/fc/{path}', video_id=item_id, *args, **kwargs)

    def _find_fanclub_site_id(self, channel_name):
        fanclub_list_json = self._call_api(
            'content_providers/channels', item_id=f'channels/{channel_name}',
            note='Fetching channel list', errnote='Unable to fetch channel list',
        )['data']['content_providers']
        fanclub_id = traverse_obj(fanclub_list_json, (
            lambda _, v: v.get('domain') == f'{self._WEBPAGE_BASE_URL}/{channel_name}', 'id'),
            get_all=False)
        if not fanclub_id:
            raise ExtractorError(f'Channel {channel_name} does not exist', expected=True)
        return fanclub_id

    def _get_channel_info(self, fanclub_site_id):
        return self._call_api(
            f'fanclub_sites/{fanclub_site_id}/page_base_info', item_id=f'fanclub_sites/{fanclub_site_id}',
            note='Fetching channel info', errnote='Unable to fetch channel info',
        )['data']['fanclub_site']


class NiconicoChannelPlusIE(NiconicoChannelPlusBaseIE):
    IE_NAME = 'NiconicoChannelPlus'
    IE_DESC = 'ニコニコチャンネルプラス'
    _VALID_URL = r'https?://nicochannel\.jp/(?P<channel>[a-z\d\._-]+)/(?:video|live)/(?P<code>sm\w+)'
    _TESTS = [{
        # real video url, normal channel name.
        'url': 'https://nicochannel.jp/kaorin/video/smsDd8EdFLcVZk9yyAhD6H7H',
        'info_dict': {
            'id': 'smsDd8EdFLcVZk9yyAhD6H7H',
            'title': '前田佳織里はニコ生がしたい！',
            'ext': 'mp4',
            'channel': '前田佳織里の世界攻略計画',
            'channel_id': 'kaorin',
            'channel_url': 'https://nicochannel.jp/kaorin',
            'live_status': 'not_live',
            'thumbnail': 'https://nicochannel.jp/public_html/contents/video_pages/74/thumbnail_path',
            'description': '２０２１年１１月に放送された\n「前田佳織里はニコ生がしたい！」アーカイブになります。',
            'timestamp': 1641360276,
            'duration': 4097,
            'comment_count': int,
            'view_count': int,
            'tags': [],
            'upload_date': '20220105',
        },
        'params': {
            'skip_download': True,
        },
    }, {
        # real video url, numbers in channel name.
        'url': 'https://nicochannel.jp/dateno8noba/video/smVGqtKpdmva4Mcrw7rbeQ8Y',
        'only_matching': True,
    }, {
        # real video url, hyphens in channel name.
        'url': 'https://nicochannel.jp/owstv-plus/video/smUPTNizUxVspEu5YeDtV3VB',
        'only_matching': True,
    }, {
        # real video url, underscores in channel name.
        'url': 'https://nicochannel.jp/sakaguchi_kugimiya/video/smieBu2u2kDTYCvYZmLvUaUN',
        'only_matching': True,
    }, {
        # real video url, dots in channel name.
        'url': 'https://nicochannel.jp/kanase.ito/video/smWCdanZc5bJYMPYhpVp6Sn6',
        'only_matching': True,
    }, {
        # fake live url, normal channel name.
        'url': 'https://nicochannel.jp/example/live/sm3Xample',
        'info_dict': {
            'id': 'sm3Xample',
            'ext': 'mp4',
        },
        'params': {
            'skip_download': False,
        },
        'skip': '404 Not Found',
    }, {
        # was real live url, but 404 now.
        'url': 'https://nicochannel.jp/matsuda_shota/live/sm5VuVsRQSRqkyvLWFZtcou7',
        'info_dict': {
            'id': 'smpptPykLAjmZQchK4k4p93P',
            'ext': 'mp4',
        },
        'params': {
            'skip_download': True,
        },
        'skip': '404 Not Found',
    }, {
        # was real live url, but 404 now.
        'url': 'https://nicochannel.jp/ayapro/live/sm8CmA9tsXUsCjwiKE59xyb6',
        'info_dict': {
            'id': 'sm8CmA9tsXUsCjwiKE59xyb6',
            'ext': 'mp4',
        },
        'params': {
            'skip_download': True,
        },
        'skip': '404 Not Found',
    }, {
        # was real live url, but no video files for download.
        'url': 'https://nicochannel.jp/tasokosyo/live/smc7pjoBytehSmMrvT9CdA9f',
        'info_dict': {
            'id': 'smc7pjoBytehSmMrvT9CdA9f',
            'ext': 'mp4',
        },
        'params': {
            'skip_download': False,
        },
        'skip': 'The downloaded file is empty',
    }]

    def _real_extract(self, url):
        content_code, channel_id = self._match_valid_url(url).group('code', 'channel')
        channel_name = self._get_channel_info(
            self._find_fanclub_site_id(channel_id)
        ).get('fanclub_site_name')

        data_json = self._call_api(
            f'video_pages/{content_code}', item_id=content_code,
            note='Fetching video page info', errnote='Unable to fetch video page info',
        )['data']['video_page']

        live_status, session_id = self._get_live_status_and_session_id(content_code, data_json)

        return {
            # mandatory metafields

            'id': content_code,
            'title': data_json['title'],
            'formats': self._extract_m3u8_formats(
                # "authenticated_url" is a format string contains "{session_id}".
                m3u8_url=data_json['video_stream']['authenticated_url'].format(session_id=session_id),
                video_id=content_code),
            'ext': 'mp4',

            # optional metafields

            '_format_sort_fields': ('tbr', 'vcodec', 'acodec'),

            'channel': channel_name,
            'channel_id': channel_id,
            'channel_url': f'{self._WEBPAGE_BASE_URL}/{channel_id}',

            'live_status': live_status,

            'thumbnail': data_json.get('thumbnail_url'),
            'description': data_json.get('description'),
            'timestamp': parse_iso8601(data_json.get('released_at'), delimiter=' '),
            'duration': int_or_none(traverse_obj(data_json, ('active_video_filename', 'length'))),
            'comment_count': int_or_none(traverse_obj(data_json, ('video_aggregate_info', 'number_of_comments'))),
            'view_count': int_or_none(traverse_obj(data_json, ('video_aggregate_info', 'total_views'))),
            'tags': traverse_obj(data_json, ('video_tags', ..., 'tag')),

            '__post_extractor': self.extract_comments(
                content_code=content_code,
                comment_group_id=traverse_obj(data_json, ('video_comment_setting', 'comment_group_id'))),
        }

    def _get_comments(self, content_code, comment_group_id):
        item_id = f'{content_code}/comments'

        if not comment_group_id:
            return None

        comment_access_token = self._call_api(
            f'video_pages/{content_code}/comments_user_token', item_id,
            note='Getting comment token', errnote='Unable to get comment token',
        )['data']['access_token']

        comment_list = self._download_json(
            'https://comm-api.sheeta.com/messages.history', video_id=item_id,
            note='Fetching comments', errnote='Unable to fetch comments',
            headers={'Content-Type': 'application/json'},
            query={
                'sort_direction': 'asc',
                'limit': traverse_obj(self._configuration_arg('max_comments', [120]), (0, )),
            },
            data=json.dumps({
                'token': comment_access_token,
                'group_id': comment_group_id,
            }).encode('ascii'))

        for comment in comment_list:
            yield {
                'author': comment.get('nickname'),
                'author_id': comment.get('sender_id'),
                'id': comment.get('id'),
                'text': comment.get('message'),
                'timestamp': int_or_none(traverse_obj(comment, 'updated_at', 'sent_at', 'created_at')),
                'author_is_uploader': comment.get('sender_id') == '-1',
            }

    def _get_live_status_and_session_id(self, content_code, data_json):
        video_type = data_json.get('type')
        live_started_at = data_json.get('live_started_at')
        live_finished_at = data_json.get('live_finished_at')

        if video_type == 'vod':
            payload = {}
            if live_finished_at:
                live_status = 'was_live'
            else:
                live_status = 'not_live'
        elif video_type == 'live':
            if not live_started_at:
                raise UserNotLive(video_id=content_code)

            if not live_finished_at:
                live_status = 'is_live'
                payload = {}
            else:
                live_status = 'was_live'
                payload = {'broadcast_type': 'dvr'}

                video_allow_dvr_flg = traverse_obj(data_json, ('video', 'allow_dvr_flg'))
                video_convert_to_vod_flg = traverse_obj(data_json, ('video', 'convert_to_vod_flg'))

                self.write_debug(f'allow_dvr_flg = {video_allow_dvr_flg}, convert_to_vod_flg = {video_convert_to_vod_flg}.')

                if not (video_allow_dvr_flg and video_convert_to_vod_flg):
                    raise ExtractorError(
                        'Live was ended, there is no video for download.', video_id=content_code, expected=True)
        else:
            # new type appears, we will handle it soon.
            raise ExtractorError(f'Unknown type: {video_type}', video_id=content_code, expected=False)

        # help us to analyze when error occurs
        self.to_screen(f'{content_code}: video_type={video_type}, live_status={live_status}')

        session_id = self._call_api(
            f'video_pages/{content_code}/session_ids', item_id=f'{content_code}/session',
            data=json.dumps(payload).encode('ascii'), headers={'Content-Type': 'application/json'},
            note='Getting session id', errnote='Unable to get session id',
        )['data']['session_id']

        return live_status, session_id


class NiconicoChannelPlusChannelBaseIE(NiconicoChannelPlusBaseIE):
    _PAGE_SIZE = 12

    def _fetch_paged_channel_video_list(self, path, query, channel_name, item_id, page):
        item_list = self._call_api(
            path, item_id, query={
                **query,
                'page': (page + 1),
                'per_page': self._PAGE_SIZE,
            },
            note=f'Getting channel info (page {page + 1})',
            errnote=f'Unable to get channel info (page {page + 1})',
        )['data']['video_pages']['list']

        for item in item_list:
            content_code = item['content_code']

            # "video/{code}" works for both VoD and live, but "live/{code}" doesn't work for VoD.
            yield self.url_result(
                f'{self._WEBPAGE_BASE_URL}/{channel_name}/video/{content_code}', NiconicoChannelPlusIE)


class NiconicoChannelPlusChannelVideosIE(NiconicoChannelPlusChannelBaseIE):
    IE_NAME = 'NiconicoChannelPlus:channel:videos'
    IE_DESC = 'ニコニコチャンネルプラス - チャンネル - 動画リスト. nicochannel.jp/channel/videos'
    _VALID_URL = r'https?://nicochannel\.jp/(?P<id>[a-z\d\._-]+)/videos(?:\?.*)?'
    _TESTS = [{
        # query: None
        'url': 'https://nicochannel.jp/testman/videos',
        'info_dict': {
            'id': 'testman-videos',
            'title': '本番チャンネルプラステストマン-videos',
        },
        'playlist_mincount': 18,
    }, {
        # query: None
        'url': 'https://nicochannel.jp/testtarou/videos',
        'info_dict': {
            'id': 'testtarou-videos',
            'title': 'チャンネルプラステスト太郎-videos',
        },
        'playlist_mincount': 2,
    }, {
        # query: None
        'url': 'https://nicochannel.jp/testjirou/videos',
        'info_dict': {
            'id': 'testjirou-videos',
            'title': 'チャンネルプラステスト二郎-videos',
        },
        'playlist_mincount': 12,
    }, {
        # query: tag
        'url': 'https://nicochannel.jp/testman/videos?tag=%E6%A4%9C%E8%A8%BC%E7%94%A8',
        'info_dict': {
            'id': 'testman-videos',
            'title': '本番チャンネルプラステストマン-videos',
        },
        'playlist_mincount': 6,
    }, {
        # query: vodType
        'url': 'https://nicochannel.jp/testman/videos?vodType=1',
        'info_dict': {
            'id': 'testman-videos',
            'title': '本番チャンネルプラステストマン-videos',
        },
        'playlist_mincount': 18,
    }, {
        # query: sort
        'url': 'https://nicochannel.jp/testman/videos?sort=-released_at',
        'info_dict': {
            'id': 'testman-videos',
            'title': '本番チャンネルプラステストマン-videos',
        },
        'playlist_mincount': 18,
    }, {
        # query: tag, vodType
        'url': 'https://nicochannel.jp/testman/videos?tag=%E6%A4%9C%E8%A8%BC%E7%94%A8&vodType=1',
        'info_dict': {
            'id': 'testman-videos',
            'title': '本番チャンネルプラステストマン-videos',
        },
        'playlist_mincount': 6,
    }, {
        # query: tag, sort
        'url': 'https://nicochannel.jp/testman/videos?tag=%E6%A4%9C%E8%A8%BC%E7%94%A8&sort=-released_at',
        'info_dict': {
            'id': 'testman-videos',
            'title': '本番チャンネルプラステストマン-videos',
        },
        'playlist_mincount': 6,
    }, {
        # query: vodType, sort
        'url': 'https://nicochannel.jp/testman/videos?vodType=1&sort=-released_at',
        'info_dict': {
            'id': 'testman-videos',
            'title': '本番チャンネルプラステストマン-videos',
        },
        'playlist_mincount': 18,
    }, {
        # query: tag, vodType, sort
        'url': 'https://nicochannel.jp/testman/videos?tag=%E6%A4%9C%E8%A8%BC%E7%94%A8&vodType=1&sort=-released_at',
        'info_dict': {
            'id': 'testman-videos',
            'title': '本番チャンネルプラステストマン-videos',
        },
        'playlist_mincount': 6,
    }]

    def _real_extract(self, url):
        """
        API parameters:
            sort:
                -released_at         公開日が新しい順 (newest to oldest)
                 released_at         公開日が古い順 (oldest to newest)
                -number_of_vod_views 再生数が多い順 (most play count)
                 number_of_vod_views コメントが多い順 (most comments)
            vod_type (is "vodType" in "url"):
                0 すべて (all)
                1 会員限定 (members only)
                2 一部無料 (partially free)
                3 レンタル (rental)
                4 生放送アーカイブ (live archives)
                5 アップロード動画 (uploaded videos)
        """

        channel_id = self._match_id(url)
        fanclub_site_id = self._find_fanclub_site_id(channel_id)
        channel_name = self._get_channel_info(fanclub_site_id).get('fanclub_site_name')
        qs = parse_qs(url)

        return self.playlist_result(
            OnDemandPagedList(
                functools.partial(
                    self._fetch_paged_channel_video_list, f'fanclub_sites/{fanclub_site_id}/video_pages',
                    filter_dict({
                        'tag': traverse_obj(qs, ('tag', 0)),
                        'sort': traverse_obj(qs, ('sort', 0), default='-released_at'),
                        'vod_type': traverse_obj(qs, ('vodType', 0), default='0'),
                    }),
                    channel_id, f'{channel_id}/videos'),
                self._PAGE_SIZE),
            playlist_id=f'{channel_id}-videos', playlist_title=f'{channel_name}-videos')


class NiconicoChannelPlusChannelLivesIE(NiconicoChannelPlusChannelBaseIE):
    IE_NAME = 'NiconicoChannelPlus:channel:lives'
    IE_DESC = 'ニコニコチャンネルプラス - チャンネル - ライブリスト. nicochannel.jp/channel/lives'
    _VALID_URL = r'https?://nicochannel\.jp/(?P<id>[a-z\d\._-]+)/lives'
    _TESTS = [{
        'url': 'https://nicochannel.jp/testman/lives',
        'info_dict': {
            'id': 'testman-lives',
            'title': '本番チャンネルプラステストマン-lives',
        },
        'playlist_mincount': 18,
    }, {
        'url': 'https://nicochannel.jp/testtarou/lives',
        'info_dict': {
            'id': 'testtarou-lives',
            'title': 'チャンネルプラステスト太郎-lives',
        },
        'playlist_mincount': 2,
    }, {
        'url': 'https://nicochannel.jp/testjirou/lives',
        'info_dict': {
            'id': 'testjirou-lives',
            'title': 'チャンネルプラステスト二郎-lives',
        },
        'playlist_mincount': 6,
    }]

    def _real_extract(self, url):
        """
        API parameters:
            live_type:
                1 放送中 (on air)
                2 放送予定 (scheduled live streams, oldest to newest)
                3 過去の放送 - すべて (all ended live streams, newest to oldest)
                4 過去の放送 - 生放送アーカイブ (all archives for live streams, oldest to newest)
            We use "4" instead of "3" because some recently ended live streams could not be downloaded.
        """

        channel_id = self._match_id(url)
        fanclub_site_id = self._find_fanclub_site_id(channel_id)
        channel_name = self._get_channel_info(fanclub_site_id).get('fanclub_site_name')

        return self.playlist_result(
            OnDemandPagedList(
                functools.partial(
                    self._fetch_paged_channel_video_list, f'fanclub_sites/{fanclub_site_id}/live_pages',
                    {
                        'live_type': 4,
                    },
                    channel_id, f'{channel_id}/lives'),
                self._PAGE_SIZE),
            playlist_id=f'{channel_id}-lives', playlist_title=f'{channel_name}-lives')
