from apify_client import ApifyClient
from backend.config import settings
import logging

logger = logging.getLogger(__name__)

class ApifyService:
    def __init__(self):
        self.client = ApifyClient(settings.APIFY_API_TOKEN)
        self.webhook_url = f"{settings.BACKEND_URL}{settings.API_PREFIX}/ingest/apify/webhook"

    def run_actor(self, actor_id: str, run_input: dict, webhook_url: str = None):
        """
        Triggers an Apify Actor run with the given input.
        Registers a webhook to call back our backend when the run finishes.
        """
        target_url = webhook_url or self.webhook_url
        try:
            # Prepare webhook to notify us when the run succeeds
            webhooks = [
                {
                    "eventTypes": ["ACTOR.RUN.SUCCEEDED"],
                    "requestUrl": target_url,
                    # Optional: Add a secret header to verify the request comes from Apify
                    # "headers": {"X-Apify-Webhook-Secret": settings.APIFY_WEBHOOK_SECRET} 
                }
            ]

            logger.info(f"Starting Apify actor {actor_id} with webhook {self.webhook_url}")
            
            # Start the actor and don't wait for it to finish (asynchronously)
            run = self.client.actor(actor_id).call(
                run_input=run_input,
                webhooks=webhooks,
                wait_secs=0 # Return immediately
            )
            
            return {
                "success": True,
                "run_id": run["id"],
                "actor_id": run["actId"]
            }
        except Exception as e:
            logger.error(f"Failed to start Apify actor: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_dataset_items(self, dataset_id: str):
        """
        Retrieves the results from a dataset.
        """
        try:
            dataset_client = self.client.dataset(dataset_id)
            items = dataset_client.list_items().items
            return items
        except Exception as e:
            logger.error(f"Failed to fetch dataset {dataset_id}: {str(e)}")
            return []

    def get_run_details(self, run_id: str):
        """
        Get details about a specific run, useful for fetching the dataset ID from a webhook payload.
        """
        try:
            return self.client.run(run_id).get()
        except Exception as e:
            logger.error(f"Failed to get run details {run_id}: {str(e)}")
            return None

    async def call_actor(self, actor_id: str, run_input: dict, timeout_secs: int = 300) -> Optional[str]:
        """
        Calls an Apify actor synchronously (waiting for finish) but non-blocking to the event loop.
        Returns the default dataset ID if successful.
        """
        import asyncio
        
        loop = asyncio.get_running_loop()
        
        def _run():
             return self.client.actor(actor_id).call(
                run_input=run_input,
                wait_secs=timeout_secs
            )
            
        try:
            logger.info(f"Calling Apify actor {actor_id}...")
            run = await loop.run_in_executor(None, _run)
            if run and run.get("status") == "SUCCEEDED":
                logger.info(f"Apify run {run.get('id')} succeeded.")
                return run.get("defaultDatasetId")
            else:
                logger.error(f"Apify run failed or timed out. Status: {run.get('status') if run else 'Unknown'}")
                return None
        except Exception as e:
            logger.error(f"Failed to call Apify actor {actor_id}: {str(e)}")
            return None

    async def get_dataset_items_async(self, dataset_id: str):
        """
        Retrieves the results from a dataset asynchronously (wrapping sync client).
        """
        import asyncio
        
        loop = asyncio.get_running_loop()
        
        def _fetch():
            dataset_client = self.client.dataset(dataset_id)
            return dataset_client.list_items().items
            
        try:
            items = await loop.run_in_executor(None, _fetch)
            return items
        except Exception as e:
            logger.error(f"Failed to fetch dataset {dataset_id}: {str(e)}")
            return []

apify_service = ApifyService()
