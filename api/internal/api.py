from typing import Dict, List, Optional

from ninja import Router
from ninja_extra import NinjaExtraAPI
from ninja_extra.exceptions import APIException

import api_logging as logging
from account.api import handle_check_allow_list, handle_get_credential_definition
from account.models import Community
from ceramic_cache.api.schema import GetStampsWithV2ScoreResponse
from ceramic_cache.api.v1 import handle_get_scorer_weights
from cgrants.api import (
    ContributorStatistics,
    handle_get_contributor_statistics,
)
from embed.api import (
    AccountAPIKeySchema,
    AddStampsPayload,
    handle_embed_add_stamps,
    handle_get_score,
    handle_validate_embed_api_key,
)
from registry.api.schema import GtcEventsResponse
from registry.api.utils import ApiKey, with_read_db
from registry.api.v1 import handle_get_gtc_stake_legacy
from registry.exceptions import aapi_get_object_or_404
from stake.api import handle_get_gtc_stake
from stake.schema import ErrorMessageResponse, StakeResponse
from v2.api.api_stamps import ahandle_scoring
from v2.schema import V2ScoreResponse

from .api_key import internal_api_key
from .bans_revocations import handle_check_bans, handle_check_revocations
from .schema import (
    CheckBanResult,
    Credential,
    RevocationCheckPayload,
    RevocationCheckResponse,
)

api_router = Router()

api = NinjaExtraAPI(
    urls_namespace="internal",
    title="Internal API",
    description="Endpoints for internal use.",
)


api.add_router("", api_router)

log = logging.getLogger(__name__)


@api_router.post("/check-bans", response=List[CheckBanResult], auth=internal_api_key)
def check_bans(request, payload: List[Credential]) -> List[CheckBanResult]:
    return handle_check_bans(payload)


@api_router.post(
    "/check-revocations", response=List[RevocationCheckResponse], auth=internal_api_key
)
def check_revocations(
    request, payload: RevocationCheckPayload
) -> List[RevocationCheckResponse]:
    return handle_check_revocations(payload)


@api_router.get(
    "/stake/gtc/{str:address}",
    auth=internal_api_key,
    response={
        200: StakeResponse,
        400: ErrorMessageResponse,
    },
    summary="Retrieve GTC stake amounts for the GTC Staking stamp",
    description="Get self and community GTC stakes for an address",
)
def get_gtc_stake(request, address: str) -> StakeResponse:
    return handle_get_gtc_stake(address)


@api_router.get(
    "/stake/legacy-gtc/{str:address}/{int:round_id}",
    auth=internal_api_key,
    response=GtcEventsResponse,
    summary="Retrieve GTC stake amounts from legacy staking contract",
    description="Get self and community GTC staking amounts based on address and round ID",
)
def get_gtc_stake_legacy(request, address: str, round_id: int) -> GtcEventsResponse:
    return handle_get_gtc_stake_legacy(address, round_id)


@api_router.get(
    "/cgrants/contributor_statistics",
    response=ContributorStatistics,
    auth=internal_api_key,
)
def cgrants_contributor_statistics(request, address: str):
    return handle_get_contributor_statistics(address)


@api_router.get(
    "/score/v2/{int:scorer_id}/{str:address}",
    response=V2ScoreResponse,
    auth=internal_api_key,
)
async def get_score_v2(
    request,
    scorer_id: int,
    address: str,
) -> V2ScoreResponse:
    community = await aapi_get_object_or_404(with_read_db(Community), id=scorer_id)
    score = await ahandle_scoring(address, community)

    if score.error is not None:
        raise APIException("Failed to calculate score.")

    return score


# TODO: check authentication for these endpoints. Ideally the embed service requires an internal
# API key, but the lambda for this one is only exposed on internal LB
@api_router.post(
    "/embed/stamps/{str:address}",
    auth=internal_api_key,
    response={
        200: GetStampsWithV2ScoreResponse,
        401: ErrorMessageResponse,
        400: ErrorMessageResponse,
        404: ErrorMessageResponse,
    },
    summary="Add Stamps and get the new score",
)
def add_stamps(
    request, address: str, payload: AddStampsPayload
) -> GetStampsWithV2ScoreResponse:
    return handle_embed_add_stamps(address, payload)


@api_router.get(
    "/embed/weights",
    response={
        200: Dict[str, float],
    },
    summary="Retrieve the embed weights",
)
def get_embed_weights(request, community_id: Optional[str] = None) -> Dict[str, float]:
    return handle_get_scorer_weights(community_id)


@api_router.get(
    "/embed/score/{int:scorer_id}/{str:address}",
    response={
        200: GetStampsWithV2ScoreResponse,
        401: ErrorMessageResponse,
        400: ErrorMessageResponse,
        404: ErrorMessageResponse,
    },
    summary="Retrieve the embed weights",
)
def get_embed_score(
    request, scorer_id: int, address: str
) -> GetStampsWithV2ScoreResponse:
    try:
        return handle_get_score(scorer_id, address)
    except Community.DoesNotExist:
        return 400, {"detail": "Invalid scorer_id"}


@api_router.get(
    "/embed/validate-api-key",
    # Here we want to authenticate the partners key, hence this ApiKey auth class
    auth=ApiKey(),
    response={
        200: AccountAPIKeySchema,
        401: ErrorMessageResponse,
        400: ErrorMessageResponse,
        404: ErrorMessageResponse,
    },
    summary="Add Stamps and get the new score",
)
def validate_api_key(request) -> AccountAPIKeySchema:
    return handle_validate_embed_api_key(request)


@api.get(
    "/allow-list/{str:list}/{str:address}",
    auth=internal_api_key,
    summary="Check if an address is on the allow list for a specific round",
)
def check_on_allow_list(request, list: str, address: str):
    return handle_check_allow_list(list, address)


@api.get("/customization/credential/{provider_id}", auth=internal_api_key)
def get_credential_definition(request, provider_id: str):
    return handle_get_credential_definition(provider_id)
