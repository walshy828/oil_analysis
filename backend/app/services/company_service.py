import re
from typing import Optional
from sqlalchemy.orm import Session
from app.models import Company, CompanyAlias


def normalize_company_name(name: str) -> str:
    """Normalize company name by removing extra whitespace, standardizing case."""
    if not name:
        return ""
    # Collapse multiple spaces, strip leading/trailing, uppercase
    normalized = " ".join(name.split()).strip().upper()
    # Remove common suffixes for matching
    normalized = re.sub(r'\s+(INC\.?|LLC\.?|CO\.?|OIL|HEATING)$', '', normalized)
    return normalized


def find_or_create_company(db: Session, raw_name: str, website: Optional[str] = None, phone: Optional[str] = None) -> Company:
    """
    Find an existing company by name or alias, or create a new one.
    Uses normalized names to improve matching.
    Updates website and phone if found and missing.
    """
    # Normalize the incoming name
    normalized_name = normalize_company_name(raw_name)
    display_name = " ".join(raw_name.split()).strip().upper()  # Keep full name for display
    
    if not normalized_name:
        raise ValueError("Company name cannot be empty")
    
    # 1. Check if exact match on normalized primary name exists
    company = db.query(Company).filter(
        Company.name == display_name
    ).first()
    
    if company:
        # If this company was merged into another, use that one
        if company.merged_into_id:
            company = db.query(Company).filter(Company.id == company.merged_into_id).first()
        
        # Update metadata if provided and allowed (prefer new data if old is missing)
        if company:
            params_updated = False
            if website and (not company.website or (website != company.website and 'click.asp' not in website)):
                company.website = website
                params_updated = True
            if phone and not company.phone:
                company.phone = phone
                params_updated = True
            
            if params_updated:
                db.commit()
                
        return company
    
    # 2. Check if an alias matches
    alias = db.query(CompanyAlias).filter(
        CompanyAlias.alias_name == display_name
    ).first()
    
    if alias:
        return alias.company
    
    # 3. Robust matching using normalized comparison
    # Pull candidates starting with the first significant word to minimize DB load
    # then compare normalized versions in Python.
    first_word = normalized_name.split(' ')[0]
    
    if len(first_word) >= 3:
        candidates = db.query(Company).filter(
            Company.name.ilike(f"{first_word}%")
        ).all()
        
        for company in candidates:
            # Check if this company was merged
            if company.merged_into_id:
               # We skip merged sources in candidates and only deal with them if we match exactly?
               # Actually, we should probably follow the merge pointer immediately if we match the source.
               pass

            if normalize_company_name(company.name) == normalized_name:
                # Found a match!
                
                # If merged, follow the chain
                if company.merged_into_id:
                     real_company = db.query(Company).filter(Company.id == company.merged_into_id).first()
                     if real_company:
                         company = real_company

                # Create alias if the display name differs significantly (e.g. clean vs dirty)
                if company.name != display_name:
                    existing_alias = db.query(CompanyAlias).filter(
                        CompanyAlias.alias_name == display_name,
                        CompanyAlias.company_id == company.id
                    ).first()
                    
                    if not existing_alias:
                        try:
                            new_alias = CompanyAlias(alias_name=display_name, company_id=company.id)
                            db.add(new_alias)
                            db.commit()
                        except:
                            db.rollback() 
                
                # Update metadata
                if website and (not company.website or (website != company.website and 'click.asp' not in website)):
                    company.website = website
                if phone and not company.phone:
                    company.phone = phone
                db.commit()

                return company
    
    # 4. No match found, create new company
    company = Company(
        name=display_name,
        website=website,
        phone=phone
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    
    return company
