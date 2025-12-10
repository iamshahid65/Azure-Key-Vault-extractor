
import os
import asyncio
import logging
import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.core.exceptions import HttpResponseError

app = func.FunctionApp()  # v2 model app registration

LOCAL_VAULT_URL  = os.getenv("LOCAL_VAULT_URL")
REMOTE_VAULT_URL = os.getenv("REMOTE_VAULT_URL")
DEFAULT_SECRET   = os.getenv("SECRET_NAME", "my-secret")

credential    = DefaultAzureCredential()
local_client  = SecretClient(vault_url=LOCAL_VAULT_URL,  credential=credential)
remote_client = SecretClient(vault_url=REMOTE_VAULT_URL, credential=credential)

async def get_with_retry(client: SecretClient, name: str, max_attempts: int = 3) -> str:
    attempt, delay = 0, 2
    while True:
        try:
            return client.get_secret(name).value
        except HttpResponseError as ex:
            attempt += 1
            if attempt >= max_attempts:
                raise ex
            await asyncio.sleep(delay)
            delay *= 2

@app.function_name(name="GetSecret")
@app.route(route="secret/{name?}", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
async def get_secret(req: func.HttpRequest) -> func.HttpResponse:
    name = req.route_params.get("name") or DEFAULT_SECRET
    try:
        value = await get_with_retry(local_client, name)
        source = "LOCAL"
    except Exception as ex_local:
        logging.warning("Local vault failed; fallback to remote: %s", ex_local)
        value = await get_with_retry(remote_client, name)
        source = "REMOTE"
    return func.HttpResponse(value, status_code=200, headers={"X-Source": source})
