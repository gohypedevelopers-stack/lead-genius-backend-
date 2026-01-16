from backend.leads.models import Lead

def calculate_score(lead: Lead, title_match: bool, company_size_match: bool) -> int:
    # score = 
    # titleMatch ? 40 : 0 +
    # companySizeMatch ? 30 : 0 +
    # enriched ? 30 : 0;
    
    score = 0
    if title_match:
        score += 40
    if company_size_match:
        score += 30
    if lead.enrichment_status == "enriched":
        score += 30
        
    return score
