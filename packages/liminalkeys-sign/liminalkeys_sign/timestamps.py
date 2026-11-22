"""RFC 3161 timestamp helpers (MCP passthrough)."""

from __future__ import annotations

from asn1crypto import cms, tsp
from pyhanko.sign.timestamps.api import TimeStamper
from pyhanko.sign.timestamps.common_utils import TimestampRequestError, handle_tsp_response


class PassthroughTimeStamper(TimeStamper):
    """
    Embed a pre-fetched TimeStampResp from Liminal Keys MCP ``timestamp`` tool.

    pyHanko calls :meth:`async_timestamp` with the SHA-256 message imprint of the
    CMS signature value; the passthrough token must match.
    """

    def __init__(self, timestamp_response_der: bytes, *, strict_imprint: bool = True):
        super().__init__(include_nonce=False)
        self._response = tsp.TimeStampResp.load(timestamp_response_der)
        self._strict_imprint = strict_imprint
        token = self._response["time_stamp_token"]
        if token is None:
            raise TimestampRequestError("TimeStampResp contains no time_stamp_token.")
        # Register for size estimation during dry runs elsewhere.
        self._register_dummy("sha256", token)

    async def async_request_tsa_response(
        self, req: tsp.TimeStampReq
    ) -> tsp.TimeStampResp:
        if self._strict_imprint:
            req_imprint = req["message_imprint"]["hashed_message"].native
            tst = self._response["time_stamp_token"]
            tst_info = tst["content"]["encap_content_info"]["content"].parsed
            ts_imprint = tst_info["message_imprint"]["hashed_message"].native
            if req_imprint != ts_imprint:
                raise TimestampRequestError(
                    "MCP timestamp token imprint does not match the signature imprint."
                )
        return self._response

    async def async_timestamp(
        self, message_digest: bytes, md_algorithm: str
    ) -> cms.ContentInfo:
        _, req = self.request_cms(message_digest, md_algorithm)
        res = await self.async_request_tsa_response(req)
        return handle_tsp_response(res, None)
