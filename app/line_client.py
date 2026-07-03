from __future__ import annotations

from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    ImageMessage,
    MessagingApi,
    PushMessageRequest,
    ReplyMessageRequest,
    TextMessage,
)


class LineClient:
    def __init__(self, access_token: str):
        self.enabled = bool(access_token)
        self.configuration = Configuration(access_token=access_token) if access_token else None

    def reply(self, reply_token: str, text: str) -> None:
        if not self.enabled:
            return
        with ApiClient(self.configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token, messages=[TextMessage(text=text[:5000])]
                )
            )

    def push_text(self, user_id: str, text: str) -> None:
        if not self.enabled:
            return
        with ApiClient(self.configuration) as api_client:
            MessagingApi(api_client).push_message(
                PushMessageRequest(to=user_id, messages=[TextMessage(text=text[:5000])])
            )

    def push_image(self, user_id: str, url: str) -> None:
        if not self.enabled:
            return
        with ApiClient(self.configuration) as api_client:
            MessagingApi(api_client).push_message(
                PushMessageRequest(
                    to=user_id,
                    messages=[ImageMessage(original_content_url=url, preview_image_url=url)],
                )
            )
