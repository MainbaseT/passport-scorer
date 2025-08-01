from typing import Any, List

from asgiref.sync import async_to_sync
from django.conf import settings
from ninja import Router, Schema
from ninja_extra import NinjaExtraAPI

import api_logging as logging
from account.models import Community
from ceramic_cache.api.schema import (
    CacheStampPayload,
    GetStampsWithV2ScoreResponse,
)
from ceramic_cache.api.v1 import handle_add_stamps_only
from ceramic_cache.models import CeramicCache
from registry.api.utils import (
    is_valid_address,
)
from registry.exceptions import (
    InvalidAddressException,
)
from v2.api import handle_scoring_for_account

api_router = Router()

api = NinjaExtraAPI(
    urls_namespace="embed",
    title="Internal API",
    description="Endpoints for internal use.",
)


api.add_router("", api_router)

log = logging.getLogger(__name__)


class AddStampsPayload(Schema):
    scorer_id: int
    stamps: List[Any]


# Endpoint for this defined in internal module
def handle_embed_add_stamps(
    address: str, payload: AddStampsPayload
) -> GetStampsWithV2ScoreResponse:
    address_lower = address.lower()
    if not is_valid_address(address_lower):
        raise InvalidAddressException()

    add_stamps_payload = [
        CacheStampPayload(
            address=address_lower,
            provider=stamp.get("credentialSubject", {}).get("provider"),
            stamp=stamp,
        )
        for stamp in payload.stamps
    ]

    try:
        added_stamps = handle_add_stamps_only(
            address, add_stamps_payload, CeramicCache.SourceApp.EMBED, payload.scorer_id
        )
        user_account = Community.objects.get(id=payload.scorer_id).account
        score = async_to_sync(handle_scoring_for_account)(
            address, payload.scorer_id, user_account
        )

        return GetStampsWithV2ScoreResponse(**added_stamps.model_dump(), score=score)
    except Exception as e:
        log.error("Error in add_stamps: %s", e)
        import traceback

        traceback.print_exc()
        raise e


class AccountAPIKeySchema(Schema):
    embed_rate_limit: str | None


def handle_validate_embed_api_key(request) -> AccountAPIKeySchema:
    """
    Return the capabilities allocated to this API key.
    This API is intended to be used in the embed service in the passport repo
    """
    return AccountAPIKeySchema.from_orm(request.api_key)


def handle_get_score(scorer_id: str, address: str) -> GetStampsWithV2ScoreResponse:
    """
    Get the score for a given address and scorer_id
    """
    try:
        if int(scorer_id) < 0:
            scorer_id = settings.DEMO_API_SCORER_ID
    except ValueError:
        pass

    address_lower = address.lower()

    user_account = Community.objects.get(id=scorer_id).account

    score = async_to_sync(handle_scoring_for_account)(
        address_lower, scorer_id, user_account
    )

    return GetStampsWithV2ScoreResponse(
        success=True,
        score=score,
        stamps=CeramicCache.objects.filter(
            address=address_lower,
            type=CeramicCache.StampType.V1,
            deleted_at__isnull=True,
            revocation__isnull=True,
        ),
    )
