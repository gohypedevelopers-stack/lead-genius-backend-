import asyncio

async def enrich_lead_data(linkedin_url: str):
    # Mock latency
    await asyncio.sleep(1)
    
    # Mock result based on URL or random
    if "error" in linkedin_url:
        raise Exception("Enrichment failed")
    
    return {
        "work_email": f"contact@{linkedin_url.split('/')[-1] or 'company'}.com",
        "company_size": "50-200",
        "enrichment_status": "enriched"
    }
