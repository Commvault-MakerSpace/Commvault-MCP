# --------------------------------------------------------------------------
# Copyright Commvault Systems, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# --------------------------------------------------------------------------
# Modified from Commvault/commvault-mcp-server for cv-mcp.
"""Slim client, client group and subclient payloads for the model."""

from __future__ import annotations

from typing import Any


def get_basic_client_group_details(api_response: dict[str, Any]) -> dict[str, Any]:
    """Client groups as id, name, client count and company; drops activity flags and discovery rules."""
    filtered = []
    for g in api_response.get("groups", []):
        cg = g.get("clientGroup", {}) or {}
        entity = cg.get("entityInfo", {}) or {}
        filtered.append(
            {
                "clientGroupId": cg.get("clientGroupId", g.get("Id")),
                "clientGroupName": g.get("name"),
                "clientCount": g.get("clientCount"),
                "companyName": entity.get("companyName"),
            }
        )
    return {"totalClientGroups": len(filtered), "clientGroups": filtered}


def filter_subclient_response(api_response: dict[str, Any]) -> dict[str, Any]:
    """Subclients as entity ids and names only; drops content and storage settings."""
    relevant_keys = [
        "clientName",
        "instanceName",
        "displayName",
        "backupsetId",
        "instanceId",
        "subclientId",
        "appName",
        "backupsetName",
        "subclientName",
    ]
    filtered = []
    for subclient in api_response.get("subClientProperties", []):
        entity = subclient.get("subClientEntity", {})
        filtered.append({k: entity.get(k) for k in relevant_keys if k in entity})
    return {"subClientCount": api_response.get("filterQueryCount", len(filtered)), "subClients": filtered}


def filter_client_list_response(response: dict[str, Any]) -> dict[str, Any]:
    """Clients as name, id, display name and host name; drops ports, properties and entity info."""
    filtered_clients = []
    for item in response.get("clientProperties", []):
        client_entity = item.get("client", {}).get("clientEntity", {})
        entry = {
            "clientName": client_entity.get("clientName"),
            "clientId": client_entity.get("clientId"),
            "hostName": client_entity.get("hostName"),
        }
        if client_entity.get("displayName") and client_entity.get("displayName") != entry["clientName"]:
            entry["displayName"] = client_entity.get("displayName")
        filtered_clients.append(entry)
    return {"totalClients": len(filtered_clients), "clients": filtered_clients}
