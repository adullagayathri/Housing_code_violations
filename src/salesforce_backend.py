import base64
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
import streamlit as st


API_VERSION = "v62.0"
SF_AUTH_URL = "https://login.salesforce.com/services/oauth2/token"


class SalesforceAPIError(Exception):
    pass


def salesforce_is_configured() -> bool:
    return bool(
        st.secrets.get("SF_CONSUMER_KEY")
        and st.secrets.get("SF_CONSUMER_SECRET")
    )


def _sf_error_message(resp: requests.Response) -> str:
    try:
        body = resp.json()
        if isinstance(body, list) and body:
            first = body[0]
            code = first.get("errorCode") or first.get("error")
            msg = first.get("message") or first.get("error_description") or str(first)
            return f"{code}: {msg}" if code else msg
        if isinstance(body, dict):
            code = body.get("errorCode") or body.get("error")
            msg = body.get("message") or body.get("error_description") or str(body)
            return f"{code}: {msg}" if code else msg
        return str(body)
    except Exception:
        return resp.text or f"HTTP {resp.status_code}"


@st.cache_resource
def get_salesforce_auth() -> Tuple[str, str]:
    if not salesforce_is_configured():
        raise SalesforceAPIError(
            "Salesforce is not configured yet. Add SF_CONSUMER_KEY and SF_CONSUMER_SECRET to secrets."
        )

    payload = {
        "grant_type": "client_credentials",
        "client_id": st.secrets["SF_CONSUMER_KEY"],
        "client_secret": st.secrets["SF_CONSUMER_SECRET"],
    }

    resp = requests.post(SF_AUTH_URL, data=payload, timeout=30)
    if not resp.ok:
        raise SalesforceAPIError(f"Salesforce auth failed: {_sf_error_message(resp)}")

    data = resp.json()
    access_token = data.get("access_token")
    instance_url = data.get("instance_url")

    if not access_token or not instance_url:
        raise SalesforceAPIError("Salesforce auth response missing access_token or instance_url.")

    return access_token, instance_url.rstrip("/")


def sf_request(
    method: str,
    path: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 60,
) -> requests.Response:
    token, instance_url = get_salesforce_auth()

    req_headers = {
        "Authorization": f"Bearer {token}",
    }
    if headers:
        req_headers.update(headers)

    resp = requests.request(
        method=method,
        url=f"{instance_url}{path}",
        params=params,
        json=json_body,
        headers=req_headers,
        timeout=timeout,
    )

    if not resp.ok:
        raise SalesforceAPIError(_sf_error_message(resp))

    return resp


def soql_query(query: str) -> List[Dict[str, Any]]:
    resp = sf_request(
        "GET",
        f"/services/data/{API_VERSION}/query",
        params={"q": query},
    )
    return resp.json().get("records", [])


def upload_image_to_salesforce(image_name: str, image_bytes: bytes) -> Tuple[str, str]:
    payload = {
        "Title": image_name.rsplit(".", 1)[0],
        "PathOnClient": image_name,
        "VersionData": base64.b64encode(image_bytes).decode("utf-8"),
        "ContentLocation": "S",
    }

    library_id = st.secrets.get("SF_LIBRARY_ID")
    if library_id:
        payload["ContentWorkspaceId"] = library_id

    resp = sf_request(
        "POST",
        f"/services/data/{API_VERSION}/sobjects/ContentVersion",
        json_body=payload,
    )

    content_version_id = resp.json()["id"]

    rows = soql_query(
        f"SELECT Id, ContentDocumentId FROM ContentVersion WHERE Id = '{content_version_id}' LIMIT 1"
    )
    if not rows:
        raise SalesforceAPIError("Could not fetch ContentDocumentId for uploaded image.")

    content_document_id = rows[0]["ContentDocumentId"]
    return content_version_id, content_document_id


def create_image_record(image_name: str, json_text: str) -> str:
    try:
        json.loads(json_text)
    except json.JSONDecodeError as e:
        raise SalesforceAPIError(
            f"JSON is invalid: {e.msg} at line {e.lineno}, column {e.colno}"
        )

    payload = {
        "Name": f"{image_name.rsplit('.', 1)[0]} - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "JSON_Data__c": json_text,
        "Image_Name__c": image_name,
        "Uploaded_At__c": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    resp = sf_request(
        "POST",
        f"/services/data/{API_VERSION}/sobjects/Image_Record__c",
        json_body=payload,
    )
    return resp.json()["id"]


def link_document_to_record(content_document_id: str, record_id: str) -> str:
    payload = {
        "ContentDocumentId": content_document_id,
        "LinkedEntityId": record_id,
        "ShareType": "V",
        "Visibility": "AllUsers",
    }

    resp = sf_request(
        "POST",
        f"/services/data/{API_VERSION}/sobjects/ContentDocumentLink",
        json_body=payload,
    )
    return resp.json()["id"]


def save_submission_to_salesforce(
    *,
    image_name: str,
    image_bytes: bytes,
    json_text: str,
) -> str:
    _, content_document_id = upload_image_to_salesforce(image_name, image_bytes)
    record_id = create_image_record(image_name, json_text)
    link_document_to_record(content_document_id, record_id)
    return record_id


@st.cache_data(ttl=60)
def fetch_recent_salesforce_records(limit: int = 50) -> List[Dict[str, Any]]:
    if not salesforce_is_configured():
        return []

    records = soql_query(
        "SELECT Id, Name, JSON_Data__c, Image_Name__c, Uploaded_At__c "
        "FROM Image_Record__c "
        "ORDER BY Uploaded_At__c DESC "
        f"LIMIT {limit}"
    )
    return records