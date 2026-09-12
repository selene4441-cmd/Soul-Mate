// Generated from packages/contracts/openapi.json. Do not edit by hand.
export type ApiMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
export type ApiOperation = {
  method: ApiMethod;
  path: string;
  operationId: string;
  tags: string[];
};

export const apiOperations = [
  {
    "method": "GET",
    "path": "/api/v1/health",
    "operationId": "health_api_v1_health_get",
    "tags": [
      "system"
    ]
  },
  {
    "method": "POST",
    "path": "/api/v1/auth/register",
    "operationId": "register_api_v1_auth_register_post",
    "tags": [
      "auth"
    ]
  },
  {
    "method": "POST",
    "path": "/api/v1/auth/login",
    "operationId": "login_api_v1_auth_login_post",
    "tags": [
      "auth"
    ]
  },
  {
    "method": "GET",
    "path": "/api/v1/auth/me",
    "operationId": "me_api_v1_auth_me_get",
    "tags": [
      "auth"
    ]
  },
  {
    "method": "POST",
    "path": "/api/v1/auth/logout",
    "operationId": "logout_api_v1_auth_logout_post",
    "tags": [
      "auth"
    ]
  },
  {
    "method": "GET",
    "path": "/api/v1/consents",
    "operationId": "get_consents_api_v1_consents_get",
    "tags": [
      "consent"
    ]
  },
  {
    "method": "POST",
    "path": "/api/v1/consents",
    "operationId": "create_consent_api_v1_consents_post",
    "tags": [
      "consent"
    ]
  },
  {
    "method": "DELETE",
    "path": "/api/v1/consents/{scope}",
    "operationId": "remove_consent_api_v1_consents__scope__delete",
    "tags": [
      "consent"
    ]
  },
  {
    "method": "GET",
    "path": "/api/v1/questionnaire",
    "operationId": "questionnaire_api_v1_questionnaire_get",
    "tags": [
      "questionnaire"
    ]
  },
  {
    "method": "POST",
    "path": "/api/v1/questionnaire/submissions",
    "operationId": "create_submission_api_v1_questionnaire_submissions_post",
    "tags": [
      "questionnaire"
    ]
  },
  {
    "method": "GET",
    "path": "/api/v1/claims",
    "operationId": "get_claims_api_v1_claims_get",
    "tags": [
      "claims"
    ]
  },
  {
    "method": "POST",
    "path": "/api/v1/claims/{claim_id}/feedback",
    "operationId": "claim_feedback_api_v1_claims__claim_id__feedback_post",
    "tags": [
      "claims"
    ]
  },
  {
    "method": "PATCH",
    "path": "/api/v1/claims/{claim_id}",
    "operationId": "edit_claim_api_v1_claims__claim_id__patch",
    "tags": [
      "claims"
    ]
  },
  {
    "method": "DELETE",
    "path": "/api/v1/claims/{claim_id}",
    "operationId": "remove_claim_api_v1_claims__claim_id__delete",
    "tags": [
      "claims"
    ]
  },
  {
    "method": "POST",
    "path": "/api/v1/recommendations",
    "operationId": "create_recommendations_api_v1_recommendations_post",
    "tags": [
      "matching"
    ]
  },
  {
    "method": "GET",
    "path": "/api/v1/recommendations/{candidate_id}",
    "operationId": "get_recommendation_api_v1_recommendations__candidate_id__get",
    "tags": [
      "matching"
    ]
  },
  {
    "method": "POST",
    "path": "/api/v1/recommendations/{candidate_id}/actions",
    "operationId": "create_action_api_v1_recommendations__candidate_id__actions_post",
    "tags": [
      "matching"
    ]
  },
  {
    "method": "POST",
    "path": "/api/v1/invitations",
    "operationId": "create_invitation_api_v1_invitations_post",
    "tags": [
      "interaction"
    ]
  },
  {
    "method": "GET",
    "path": "/api/v1/matches",
    "operationId": "get_matches_api_v1_matches_get",
    "tags": [
      "interaction"
    ]
  },
  {
    "method": "GET",
    "path": "/api/v1/matches/{match_id}/messages",
    "operationId": "get_messages_api_v1_matches__match_id__messages_get",
    "tags": [
      "interaction"
    ]
  },
  {
    "method": "POST",
    "path": "/api/v1/matches/{match_id}/messages",
    "operationId": "create_message_api_v1_matches__match_id__messages_post",
    "tags": [
      "interaction"
    ]
  },
  {
    "method": "GET",
    "path": "/api/v1/outcomes",
    "operationId": "get_outcomes_api_v1_outcomes_get",
    "tags": [
      "outcomes"
    ]
  },
  {
    "method": "POST",
    "path": "/api/v1/outcomes",
    "operationId": "create_outcome_api_v1_outcomes_post",
    "tags": [
      "outcomes"
    ]
  },
  {
    "method": "POST",
    "path": "/api/v1/safety/reports",
    "operationId": "create_report_api_v1_safety_reports_post",
    "tags": [
      "safety"
    ]
  },
  {
    "method": "GET",
    "path": "/api/v1/admin/safety-events",
    "operationId": "safety_events_api_v1_admin_safety_events_get",
    "tags": [
      "admin"
    ]
  },
  {
    "method": "PATCH",
    "path": "/api/v1/admin/safety-events/{event_id}",
    "operationId": "update_safety_event_api_v1_admin_safety_events__event_id__patch",
    "tags": [
      "admin"
    ]
  },
  {
    "method": "GET",
    "path": "/api/v1/admin/versions",
    "operationId": "versions_api_v1_admin_versions_get",
    "tags": [
      "admin"
    ]
  },
  {
    "method": "DELETE",
    "path": "/api/v1/privacy/me",
    "operationId": "delete_me_api_v1_privacy_me_delete",
    "tags": [
      "privacy"
    ]
  }
] as const satisfies readonly ApiOperation[];
