# -*- coding: utf-8 -*-
"""
Opportunity One — Alexa custom skill (Alexa-hosted, Python, ask-sdk-core).

Conversation:
  1. Asks gender, age and yearly family income (in any order, can be corrected).
  2. Says how many schemes and internships match; user picks "schemes" or "internships".
  3. Reads the list 3 at a time ("next" for more); user picks by number or by name.
  4. Gives eligibility + the required documents, asks which ones are missing,
     explains how to get each missing one, then offers the steps to apply.

Uses only ask-sdk-core (already in the Alexa-hosted requirements.txt).
Eligibility is a guide, never a guarantee. Records marked sample are fictional.
"""

import logging
import re

from ask_sdk_core.dispatch_components import AbstractExceptionHandler
from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.utils import is_intent_name, is_request_type
from ask_sdk_model.ui import SimpleCard

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

SKILL_NAME = "Opportunity One"
CHECKED_ON = "23 Oct 2026"

# =============================================================================
# Slot values (single source of truth; the interaction model is generated from it)
# First entry of each list = value name, the rest = synonyms. Key = value id.
# =============================================================================
SLOT_TYPES = {
    "GenderType": {
        "female": ["female", "girl", "woman", "lady", "women", "mahila", "ladki", "a girl", "a woman"],
        "male": ["male", "boy", "man", "gentleman", "ladka", "purush", "a boy", "a man"],
        "other": ["other", "transgender", "non binary", "third gender", "prefer not to say", "i don't want to say"],
    },
    "CategoryType": {
        "scheme": ["schemes", "scheme", "government schemes", "government scheme", "scholarships", "scholarship",
                   "yojana", "yojanas", "sarkari yojana", "benefits", "government benefits"],
        "internship": ["internships", "internship", "interns", "intern", "training", "apprenticeships"],
    },
    "IncomeUnitType": {
        "lakh": ["lakh", "lakhs", "lac", "lacs", "lakh rupees", "lakhs rupees", "lakh per year", "lakh per annum",
                 "lakh a year", "lakh yearly", "l p a"],
        "thousand": ["thousand", "thousand rupees", "k"],
        "crore": ["crore", "crores", "crore rupees"],
        "rupees": ["rupees", "rupee", "rs", "rupees per year", "rupees a year"],
    },
    "OpportunityType": {
        "csss": ["central sector scholarship", "central sector scheme", "central sector scheme of scholarship",
                 "central scholarship", "national scholarship", "n s p scholarship"],
        "pragati": ["pragati", "pragati scholarship", "aicte pragati", "a i c t e pragati", "scholarship for girls",
                    "girls scholarship"],
        "vidyalaxmi": ["vidyalaxmi", "vidya laxmi", "vidya lakshmi", "pm vidyalaxmi", "education loan", "student loan"],
        "apy": ["atal pension", "atal pension yojana", "a p y", "pension scheme", "pension yojana"],
        "pmjjby": ["jeevan jyoti", "jeevan jyoti bima", "jeevan jyoti bima yojana", "life insurance", "p m j j b y"],
        "pmsby": ["suraksha bima", "suraksha bima yojana", "accident insurance", "p m s b y"],
        "standup": ["stand up india", "standup india", "stand up", "business loan", "startup loan"],
        "pmis": ["pm internship", "p m internship", "pm internship scheme", "prime minister internship",
                 "prime minister's internship", "prime minister internship scheme"],
        "niti": ["niti aayog", "niti aayog internship", "niti internship", "neeti aayog"],
        "apprentice": ["apprenticeship india", "apprenticeship", "apprentice", "naps"],
        "sample_frontend": ["frontend developer intern", "frontend intern", "frontend internship", "front end developer",
                            "frontend developer"],
        "sample_data": ["data analytics intern", "data analytics", "data analytics internship", "data internship",
                        "data analyst intern"],
    },
    "DocumentType": {
        "aadhaar": ["aadhaar card", "aadhaar", "aadhar", "aadhar card", "adhaar", "uid card"],
        "pan": ["pan card", "pan", "p a n card", "permanent account number"],
        "bank_aadhaar": ["bank account linked with aadhaar", "aadhaar linked bank account", "aadhaar seeded bank account",
                         "seeded bank account", "bank account with aadhaar"],
        "bank_account": ["bank account", "savings account", "post office account", "bank passbook", "passbook"],
        "income_cert": ["income certificate", "family income certificate", "income proof", "income document"],
        "caste_cert": ["caste certificate", "caste", "community certificate", "s c certificate", "s t certificate"],
        "marksheet_10": ["tenth marksheet", "class ten marksheet", "tenth class marksheet", "ssc marksheet",
                         "tenth certificate", "matric marksheet"],
        "marksheet_12": ["twelfth marksheet", "class twelve marksheet", "twelfth class marksheet", "intermediate marksheet",
                         "inter marksheet", "twelfth certificate", "hsc marksheet"],
        "edu_cert": ["education certificate", "qualification certificate", "degree certificate", "diploma certificate",
                     "educational certificate", "marksheet", "marks card"],
        "latest_marksheet": ["latest marksheet", "semester marksheet", "transcript", "college marksheet"],
        "bonafide": ["bonafide certificate", "bonafide", "study certificate", "student certificate"],
        "admission_letter": ["admission letter", "admission proof", "allotment letter", "offer letter from college"],
        "fee_receipt": ["fee receipt", "fee structure", "fees receipt", "tuition fee receipt"],
        "noc": ["noc", "n o c", "no objection certificate", "college noc"],
        "resume": ["resume", "cv", "c v", "biodata"],
        "photo": ["photo", "photograph", "passport photo", "passport size photo"],
        "mobile": ["mobile number", "phone number", "linked mobile number"],
        "consent_form": ["consent form", "declaration form", "enrolment form", "enrollment form"],
        "nominee": ["nominee", "nominee details"],
        "address_proof": ["address proof", "proof of address", "residence proof"],
        "project_report": ["project report", "business plan", "business proposal"],
        "premises_proof": ["rent agreement", "premises proof", "shop proof", "office proof"],
    },
}

# =============================================================================
# Documents: card text + short spoken guidance
# =============================================================================
DOCS = {
    "aadhaar": ("Aadhaar card", "your Aadhaar card",
                "Download e-Aadhaar from uidai.gov.in with your registered mobile, or visit an Aadhaar Seva Kendra.",
                "You can download e-Aadhaar from the U I D A I website using your registered mobile number, or visit an Aadhaar Seva Kendra."),
    "pan": ("PAN card", "a PAN card",
            "Apply on the Income Tax e-filing portal (instant e-PAN with Aadhaar), or through NSDL or UTIITSL.",
            "You can get an instant e-PAN for free on the Income Tax e-filing website using your Aadhaar."),
    "bank_aadhaar": ("Bank account linked (seeded) with Aadhaar", "a bank account linked with Aadhaar",
                     "Ask your bank branch or use net banking to seed Aadhaar to your savings account. Keep the passbook front page.",
                     "Visit your bank branch or use net banking to link your Aadhaar with your savings account."),
    "bank_account": ("Savings bank or post office account", "a savings bank or post office account",
                     "Open a savings account at any bank or post office with Aadhaar. Zero-balance Jan Dhan accounts are available.",
                     "Open a savings account at any bank or post office with your Aadhaar. Zero balance Jan Dhan accounts are available."),
    "income_cert": ("Family income certificate", "a family income certificate",
                    "Issued by your state revenue department (Tahsildar or MRO office). Most states allow online applications, "
                    "for example MeeSeva in Telangana and Andhra Pradesh. Usually needs Aadhaar, ration card or salary proof "
                    "and a self-declaration. Once issued it may also appear in DigiLocker.",
                    "An income certificate is issued by your state revenue department, at the Tahsildar or M R O office. "
                    "Most states let you apply online, for example through Mee Seva in Telangana. "
                    "Keep your Aadhaar, ration card or salary proof ready."),
    "caste_cert": ("Caste certificate (only if you apply as SC or ST)", "a caste certificate, only if you apply as S C or S T",
                   "Apply through your state's e-district or revenue services portal, or the Tahsildar office.",
                   "Apply for a caste certificate on your state's e district portal, or at the Tahsildar office."),
    "marksheet_10": ("Class 10 marksheet", "your class ten marksheet",
                     "Fetch it from DigiLocker if your board publishes it, or request a duplicate from your board.",
                     "You can download it from DigiLocker if your board publishes it, or ask your board for a duplicate."),
    "marksheet_12": ("Class 12 marksheet", "your class twelve marksheet",
                     "Fetch it from DigiLocker if your board publishes it, or request a certified copy from your board.",
                     "You can download it from DigiLocker if your board publishes it, or ask your board for a copy."),
    "edu_cert": ("Highest qualification certificate (10th, 12th, ITI, diploma or degree)", "your highest qualification certificate",
                 "Use your latest marksheet or certificate. Many boards and universities publish them in DigiLocker.",
                 "Use your latest marksheet or certificate. Many boards and universities publish them in DigiLocker."),
    "latest_marksheet": ("Latest semester marksheet or transcript", "your latest semester marksheet",
                         "Download it from your university portal or ask the exam section.",
                         "Download it from your university portal, or ask your college exam section."),
    "bonafide": ("Bonafide or study certificate", "a bonafide certificate from your college",
                 "Request it from your college office. It usually takes 1 to 3 working days.",
                 "Ask your college office for a bonafide certificate. It usually takes one to three working days."),
    "admission_letter": ("Admission letter", "your admission letter",
                         "Download it from your counselling portal or ask your college admissions office.",
                         "Download it from your counselling portal, or ask your college admissions office."),
    "fee_receipt": ("Fee structure or tuition fee receipt", "your fee receipt or fee structure",
                    "Get it from your college accounts office or fee portal.",
                    "Get it from your college accounts office or fee portal."),
    "noc": ("No Objection Certificate (NOC) from your college", "a no objection certificate from your college",
            "Request it from your HOD, Principal or training and placement cell, on college letterhead.",
            "Ask your head of department or training and placement cell for a no objection certificate on college letterhead."),
    "resume": ("Resume or CV", "your resume",
               "One page: education, skills, two or three projects, and links such as GitHub or a portfolio.",
               "Make a one page resume with your education, skills, and two or three projects."),
    "photo": ("Recent passport-size photo", "a passport size photo",
              "Scan it at the size and format the portal asks for, usually a small JPG.",
              "Keep a scanned passport size photo in the size the website asks for."),
    "mobile": ("Mobile number linked to Aadhaar and bank", "a mobile number linked to your Aadhaar and bank",
               "Update it at your bank branch and at an Aadhaar Seva Kendra if needed.",
               "Update your mobile number at your bank branch, and at an Aadhaar Seva Kendra if needed."),
    "consent_form": ("Scheme consent-cum-declaration form", "the scheme consent form",
                     "Get it at your bank or post office branch, or enrol through net banking or your bank's app.",
                     "Your bank or post office gives you this form. You can also enrol through net banking."),
    "nominee": ("Nominee details (name, relation, date of birth)", "your nominee's details",
                "Keep the nominee's name, relation and date of birth ready. No certificate needed.",
                "Just keep your nominee's name, relation and date of birth ready. No certificate is needed."),
    "address_proof": ("Address proof", "an address proof",
                      "Aadhaar, voter ID, passport, or a recent utility bill.",
                      "Your Aadhaar, voter I D, passport, or a recent electricity bill works as address proof."),
    "project_report": ("Business plan or project report", "a project report for your business",
                       "Write down costs, funding needed and expected revenue. The Stand-Up Mitra portal offers handholding support.",
                       "Write down your costs, the loan you need, and expected income. The Stand Up Mitra portal offers free guidance."),
    "premises_proof": ("Proof of business premises", "proof of your business premises",
                       "Rent agreement, lease deed, or property papers.",
                       "A rent agreement, lease deed, or property papers work as proof of premises."),
}

# Related documents: if the user names one of these, the matching one on the list is used.
DOC_EQUIV = {
    "bank_account": ["bank_aadhaar"], "bank_aadhaar": ["bank_account"],
    "marksheet_10": ["edu_cert"], "marksheet_12": ["edu_cert", "latest_marksheet"],
    "edu_cert": ["marksheet_12", "marksheet_10", "latest_marksheet"], "latest_marksheet": ["edu_cert", "marksheet_12"],
}

# =============================================================================
# Opportunities
# =============================================================================
OPPORTUNITIES = [
    {
        "id": "csss", "kind": "scheme",
        "title": "Central Sector Scheme of Scholarships (College and University)",
        "say": "the Central Sector Scholarship for college and university students",
        "benefit": "Rs 12,000 a year during graduation; Rs 20,000 a year at postgraduate level.",
        "say_benefit": "It gives 12,000 rupees a year during graduation, and 20,000 rupees a year for post graduation.",
        "rules": [{"field": "income", "max": 450000}],
        "confirm": ["Above the 80th percentile in your Class 12 board and stream",
                    "Studying a regular degree course (not distance, correspondence or diploma)",
                    "Not receiving any other scholarship or fee reimbursement"],
        "say_confirm": "you scored above the 80th percentile in class twelve, you study a regular degree course, and you don't get another scholarship",
        "documents": ["marksheet_12", "income_cert", "bonafide", "aadhaar", "bank_aadhaar"],
        "apply": ["Register on the National Scholarship Portal (NSP).",
                  "Apply under Central Sector Scheme of Scholarships for College and University Students.",
                  "Your institution verifies the application online."],
        "say_apply": "Register on the National Scholarship Portal, apply under the Central Sector Scheme of Scholarships, and your college will verify it online.",
        "url": "https://scholarships.gov.in", "say_url": "scholarships dot gov dot in",
    },
    {
        "id": "pragati", "kind": "scheme",
        "title": "AICTE Pragati Scholarship for Girls",
        "say": "the A I C T E Pragati Scholarship for girls",
        "benefit": "Up to Rs 50,000 a year (tuition up to Rs 30,000 plus Rs 2,000 a month for 10 months).",
        "say_benefit": "It gives up to 50,000 rupees a year for tuition and expenses.",
        "rules": [{"field": "gender", "allowed": ["female"], "maybe_for": ["other"],
                   "say_note": "this scholarship is for girl students, so please confirm with A I C T E",
                   "say_fail": "it is only for girl students"},
                  {"field": "income", "max": 800000}],
        "confirm": ["Admitted to the 1st year of a technical degree or diploma course",
                    "AICTE-approved institution, admitted through centralised counselling",
                    "At most two girl children per family"],
        "say_confirm": "you are in the first year of a technical degree or diploma at an A I C T E approved college",
        "documents": ["admission_letter", "income_cert", "marksheet_12", "fee_receipt", "aadhaar", "bank_aadhaar"],
        "apply": ["Check the current cycle on the AICTE website and the National Scholarship Portal.",
                  "Keep your admission letter and income certificate ready before you start."],
        "say_apply": "Check the current application cycle on the A I C T E website and the National Scholarship Portal.",
        "url": "https://www.aicte.gov.in", "say_url": "a i c t e dot gov dot in",
    },
    {
        "id": "vidyalaxmi", "kind": "scheme",
        "title": "PM Vidyalaxmi (education loan support)",
        "say": "P M Vidyalaxmi education loan support",
        "benefit": "Collateral-free education loans at top institutions; 3% interest subvention on loans up to Rs 10 lakh "
                   "when family income is up to Rs 8 lakh.",
        "say_benefit": "It gives education loans without collateral at top colleges, and 3 percent interest help when family income is up to 8 lakh.",
        "rules": [{"field": "income", "max": 800000, "over_is": "maybe",
                   "say_note": "you can still apply for the loan, but the interest help needs family income up to 8 lakh"}],
        "confirm": ["Admitted to a Quality Higher Education Institution (NIRF top 100, state top 200, or a central Government institution)"],
        "say_confirm": "your college is on the government's quality institutions list",
        "documents": ["admission_letter", "fee_receipt", "income_cert", "aadhaar", "pan"],
        "apply": ["Read the scheme guidelines and confirm your institution is on the Quality HEI list.",
                  "Apply through the PM Vidyalaxmi portal named in the guidelines and choose a bank."],
        "say_apply": "Check that your college is on the quality institutions list, then apply on the P M Vidyalaxmi portal and choose a bank.",
        "url": "https://education.gov.in/sites/upload_files/mhrd/files/document-reports/PM_Vidyalaxmi_Scheme_Guidelines.pdf",
        "say_url": "education dot gov dot in",
    },
    {
        "id": "apy", "kind": "scheme",
        "title": "Atal Pension Yojana (APY)",
        "say": "Atal Pension Yojana",
        "benefit": "Guaranteed monthly pension of Rs 1,000 to Rs 5,000 from age 60, depending on your contribution.",
        "say_benefit": "It gives a guaranteed monthly pension of 1,000 to 5,000 rupees from age 60.",
        "rules": [{"field": "age", "min": 18, "max": 40}],
        "confirm": ["You are not an income-tax payer (not allowed since 1 October 2022)",
                    "You have a savings bank or post office account"],
        "say_confirm": "you do not pay income tax",
        "documents": ["aadhaar", "bank_account", "mobile", "nominee"],
        "apply": ["Enrol at your bank or post office branch, or through net banking or your bank's app.",
                  "Choose your pension amount; contributions are auto-debited monthly."],
        "say_apply": "Enrol at your bank or post office, or through net banking, and choose your pension amount.",
        "url": "https://www.myscheme.gov.in/schemes/apy", "say_url": "my scheme dot gov dot in",
    },
    {
        "id": "pmjjby", "kind": "scheme",
        "title": "Pradhan Mantri Jeevan Jyoti Bima Yojana (PMJJBY)",
        "say": "Pradhan Mantri Jeevan Jyoti Bima Yojana",
        "benefit": "Rs 2 lakh life cover for Rs 436 a year.",
        "say_benefit": "It gives 2 lakh rupees of life cover for 436 rupees a year.",
        "rules": [{"field": "age", "min": 18, "max": 50}],
        "confirm": ["You have a savings bank or post office account (premium is auto-debited)"],
        "say_confirm": "you have a savings bank or post office account",
        "documents": ["aadhaar", "bank_account", "consent_form", "nominee"],
        "apply": ["Enrol at your bank or post office branch, or via net banking.",
                  "Give consent for the yearly auto-debit of the premium."],
        "say_apply": "Enrol at your bank or post office branch, or through net banking.",
        "url": "https://www.myscheme.gov.in", "say_url": "my scheme dot gov dot in",
    },
    {
        "id": "pmsby", "kind": "scheme",
        "title": "Pradhan Mantri Suraksha Bima Yojana (PMSBY)",
        "say": "Pradhan Mantri Suraksha Bima Yojana",
        "benefit": "Rs 2 lakh accident cover (death or full disability) for Rs 20 a year.",
        "say_benefit": "It gives 2 lakh rupees of accident cover for just 20 rupees a year.",
        "rules": [{"field": "age", "min": 18, "max": 70}],
        "confirm": ["You have a savings bank account (premium is auto-debited; one account per person)"],
        "say_confirm": "you have a savings bank account",
        "documents": ["aadhaar", "bank_account", "consent_form", "nominee"],
        "apply": ["Enrol at your bank branch or via net banking.",
                  "Give consent for the yearly auto-debit of the premium."],
        "say_apply": "Enrol at your bank branch, or through net banking.",
        "url": "https://www.myscheme.gov.in", "say_url": "my scheme dot gov dot in",
    },
    {
        "id": "standup", "kind": "scheme",
        "title": "Stand-Up India (loans for new businesses)",
        "say": "Stand Up India business loans",
        "benefit": "Bank loan of Rs 10 lakh to Rs 1 crore to start a new enterprise.",
        "say_benefit": "It gives a bank loan of 10 lakh to 1 crore rupees to start a new business.",
        "rules": [{"field": "age", "min": 18},
                  {"field": "gender", "allowed": ["female"], "maybe_for": ["male", "other"],
                   "say_note": "it is open to women, and to others only if they are S C or S T, so please confirm your category"}],
        "confirm": ["It is a new (greenfield) enterprise in manufacturing, services or trading",
                    "For a company or partnership: SC, ST or women owners hold at least 51%",
                    "You are not a defaulter to any bank"],
        "say_confirm": "it is a new business and you are not a bank defaulter",
        "documents": ["aadhaar", "pan", "address_proof", "caste_cert", "project_report", "premises_proof"],
        "apply": ["Register on the Stand-Up Mitra portal or approach a bank branch directly.",
                  "The bank appraises your project report and decides the final document list."],
        "say_apply": "Register on the Stand Up Mitra portal, or go to a bank branch with your project report.",
        "url": "https://www.standupmitra.in", "say_url": "standup mitra dot in",
    },
    {
        "id": "pmis", "kind": "internship",
        "title": "PM Internship Scheme",
        "say": "the P M Internship Scheme",
        "benefit": "Internship in a top company. 2026 reports: Rs 9,000 a month (earlier Rs 5,000), Rs 6,000 one-time grant "
                   "and insurance. Confirm current amounts on the portal.",
        "say_benefit": "It offers internships in top companies. Reports for 2026 say the stipend is 9,000 rupees a month, plus a one time grant of 6,000 rupees. Please confirm on the portal.",
        "rules": [{"field": "age", "min": 18, "max": 25},
                  {"field": "income", "max": 800000, "grey_max": 1200000,
                   "say_note": "sources differ on the income limit, 8 lakh or 12 lakh, so please confirm on the portal"}],
        "confirm": ["Indian citizen, not in a full-time job",
                    "If you are a student: final-year students may apply with a college NOC (2026 rules as reported)",
                    "Not a graduate of IIT, IIM, IISER, IIIT, NLU or NID",
                    "No CA, CMA, CS, MBBS, BDS, MBA or any master's degree",
                    "No immediate family member in a permanent Government job"],
        "say_confirm": "you are not in a full time job, you don't have a master's degree, and no one in your immediate family has a permanent government job",
        "documents": ["aadhaar", "edu_cert", "income_cert", "bank_aadhaar", "photo", "noc"],
        "apply": ["Register on the PM Internship portal with Aadhaar e-KYC.",
                  "Complete your profile and choose your internship preferences.",
                  "Track and accept offers on the portal."],
        "say_apply": "Register on the P M Internship portal with Aadhaar e K Y C, complete your profile, and choose your internship preferences.",
        "url": "https://pminternship.mca.gov.in", "say_url": "p m internship dot m c a dot gov dot in",
    },
    {
        "id": "niti", "kind": "internship",
        "title": "NITI Aayog Internship",
        "say": "the NITI Aayog Internship",
        "benefit": "6 weeks to 6 months of policy research in New Delhi. Unpaid (no stipend).",
        "say_benefit": "It is a 6 week to 6 month policy research internship in New Delhi. It is unpaid.",
        "rules": [],
        "confirm": ["UG: finished or appeared in 2nd-year exams, with 85% or more in Class 12",
                    "PG or PhD: finished or appeared in 1st-year exams, with 70% or more in graduation",
                    "Recent graduates: 70% or more, within 6 months of results",
                    "College NOC needed at joining"],
        "say_confirm": "you have finished second year with 85 percent or more in class twelve, or you are a post graduate with 70 percent or more in graduation",
        "documents": ["resume", "marksheet_12", "latest_marksheet", "noc"],
        "apply": ["Applications open every month on NITI Aayog's internship page.",
                  "Apply early in the month for the cycle you want."],
        "say_apply": "Applications open every month on the NITI Aayog website. Apply early in the month.",
        "url": "https://www.niti.gov.in", "say_url": "niti dot gov dot in",
    },
    {
        "id": "apprentice", "kind": "internship",
        "title": "Apprenticeship India (paid apprenticeships)",
        "say": "Apprenticeship India",
        "benefit": "Paid on-the-job training with industry under the National Apprenticeship Promotion Scheme.",
        "say_benefit": "It offers paid on the job training with companies.",
        "rules": [],
        "confirm": ["Minimum age and qualification depend on the trade; check each listing"],
        "say_confirm": "you meet the age and qualification for the trade you choose",
        "documents": ["aadhaar", "edu_cert", "bank_aadhaar", "photo"],
        "apply": ["Register as a candidate on the Apprenticeship India portal.",
                  "Apply to openings that match your trade and location."],
        "say_apply": "Register as a candidate on the Apprenticeship India portal and apply to openings near you.",
        "url": "https://www.apprenticeshipindia.gov.in", "say_url": "apprenticeship india dot gov dot in",
    },
    {
        "id": "sample_frontend", "kind": "internship", "sample": True,
        "title": "Frontend Developer Intern (SAMPLE, fictional company)",
        "say": "the Frontend Developer internship, a sample listing",
        "benefit": "Rs 15,000 a month, 6 months, hybrid in Hyderabad (sample figures).",
        "say_benefit": "It pays 15,000 rupees a month for 6 months in Hyderabad. This is a sample listing for the demo.",
        "rules": [{"field": "age", "min": 18, "max": 28}],
        "confirm": ["Comfortable with React and JavaScript"],
        "say_confirm": "you know React and JavaScript",
        "documents": ["resume", "bonafide"],
        "apply": ["Sample listing for the demo. A real integration links to the employer's page."],
        "say_apply": "This is a sample listing for the demo, so there is no real application.",
        "url": "https://example.org/opportunity-one/sample-frontend", "say_url": "the link in your Alexa app",
    },
    {
        "id": "sample_data", "kind": "internship", "sample": True,
        "title": "Data Analytics Intern (SAMPLE, fictional NGO)",
        "say": "the Data Analytics internship, a sample listing",
        "benefit": "Rs 8,000 a month, 3 months, remote (sample figures).",
        "say_benefit": "It pays 8,000 rupees a month for 3 months, from home. This is a sample listing for the demo.",
        "rules": [{"field": "age", "min": 18, "max": 30}],
        "confirm": ["Basic Python, SQL or Excel"],
        "say_confirm": "you know basic Python, S Q L, or Excel",
        "documents": ["resume"],
        "apply": ["Sample listing for the demo."],
        "say_apply": "This is a sample listing for the demo, so there is no real application.",
        "url": "https://example.org/opportunity-one/sample-data", "say_url": "the link in your Alexa app",
    },
]
OPP_BY_ID = {o["id"]: o for o in OPPORTUNITIES}

# =============================================================================
# Eligibility engine (deterministic)
# =============================================================================
OK, MAYBE, FAIL = "ok", "maybe", "fail"


def speak_inr(n):
    """350000 -> '3.5 lakh rupees' (for speech)."""
    n = int(n)
    if n >= 10000000:
        v, u = n / 10000000.0, "crore"
    elif n >= 100000:
        v, u = n / 100000.0, "lakh"
    elif n >= 1000:
        v, u = n / 1000.0, "thousand"
    else:
        return "{} rupees".format(n)
    v = round(v, 2)
    num = str(int(v)) if v == int(v) else ("%g" % v)
    return "{} {} rupees".format(num, u)


def check_rule(rule, user):
    f = rule["field"]
    if f == "age":
        lo, hi = rule.get("min", 0), rule.get("max", 200)
        if lo <= user["age"] <= hi:
            return OK, ""
        if hi >= 200:
            return FAIL, "you must be at least {}".format(lo)
        return FAIL, "the age limit is {} to {}".format(lo, hi)
    if f == "gender":
        if user["gender"] in rule["allowed"]:
            return OK, ""
        if user["gender"] in rule.get("maybe_for", []):
            return MAYBE, rule.get("say_note", "")
        return FAIL, rule.get("say_fail", "it is not open to your gender")
    if f == "income":
        inc = user["income"]
        if inc <= rule["max"]:
            return OK, ""
        if rule.get("grey_max") and inc <= rule["grey_max"]:
            return MAYBE, rule.get("say_note", "")
        if rule.get("over_is") == "maybe":
            return MAYBE, rule.get("say_note", "")
        return FAIL, "family income must be up to {} a year".format(speak_inr(rule["max"]))
    raise ValueError("unknown rule field " + f)


def evaluate(opp, user):
    """Returns (status, results); status is 'eligible', 'check' or 'not'."""
    results = [(r,) + check_rule(r, user) for r in opp["rules"]]
    states = [s for _, s, _ in results]
    if FAIL in states:
        status = "not"
    elif MAYBE in states or not results:
        status = "check"
    else:
        status = "eligible"
    return status, results


def matches_for(user, kind):
    """Ids of opportunities of this kind the user may qualify for, eligible first, samples last."""
    rows = []
    for o in OPPORTUNITIES:
        if o["kind"] != kind:
            continue
        st, _ = evaluate(o, user)
        if st != "not":
            rows.append((0 if st == "eligible" else 1, 1 if o.get("sample") else 0, o["id"]))
    rows.sort(key=lambda r: (r[0], r[1]))
    return [r[2] for r in rows]


def not_eligible(user):
    out = []
    for o in OPPORTUNITIES:
        st, res = evaluate(o, user)
        if st == "not":
            reasons = [why for _, s, why in res if s == FAIL]
            out.append((o, reasons))
    return out

# =============================================================================
# Speech helpers
# =============================================================================
STATE_ASK_GENDER = "ASK_GENDER"
STATE_ASK_AGE = "ASK_AGE"
STATE_ASK_INCOME = "ASK_INCOME"
STATE_ASK_CATEGORY = "ASK_CATEGORY"
STATE_LIST = "LIST"
STATE_NOTELIG_Q = "NOTELIG_Q"     # "You're probably not eligible. Still want the documents?"
STATE_DOC_ALL_Q = "DOC_ALL_Q"     # "Do you have all of them?"
STATE_DOC_WHICH = "DOC_WHICH"     # "Which document is missing?"
STATE_DOC_MORE_Q = "DOC_MORE_Q"   # "Is any other document missing?"
STATE_APPLY_Q = "APPLY_Q"         # "Do you want the steps to apply?"
STATE_OTHER_Q = "OTHER_Q"         # "Want to hear other schemes or internships?"

Q_GENDER = "What is your gender? You can say female, male, or other."
Q_AGE = "How old are you? Just say your age, for example, twenty one."
Q_INCOME = ("What is your family's total income in a year? "
            "For example, say three lakh, or two point five lakh.")
Q_CATEGORY = "Which would you like to hear, schemes or internships?"

PAGE = 3
KIND_WORD = {"scheme": "government schemes and scholarships", "internship": "internships"}


def join_words(items, conj="and"):
    items = list(items)
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + ", " + conj + " " + items[-1]


def clean(text):
    """Keep SSML valid: no raw &, <, >."""
    return text.replace("&", " and ").replace("<", " ").replace(">", " ")


def sess(hi):
    return hi.attributes_manager.session_attributes


def user_of(s):
    return {"gender": s.get("gender"), "age": s.get("age"), "income": s.get("income")}


def profile_complete(s):
    return s.get("gender") is not None and s.get("age") is not None and s.get("income") is not None


def respond(hi, speech, reprompt=None, end=False, card=None):
    s = sess(hi)
    speech = clean(speech)
    rb = hi.response_builder.speak(speech)
    if card:
        rb.set_card(SimpleCard(card[0], card[1]))
    if end:
        rb.set_should_end_session(True)
    else:
        reprompt = clean(reprompt or current_question(s))
        rb.ask(reprompt)
        s["last"] = speech
        s["last_reprompt"] = reprompt
    return rb.response


def current_question(s):
    st = s.get("state")
    if st == STATE_ASK_GENDER:
        return Q_GENDER
    if st == STATE_ASK_AGE:
        return Q_AGE
    if st == STATE_ASK_INCOME:
        return Q_INCOME
    if st == STATE_ASK_CATEGORY:
        return Q_CATEGORY
    if st == STATE_LIST:
        return "Say a number to choose, or say next to hear more."
    if st == STATE_NOTELIG_Q:
        return "Do you still want to hear the documents? Say yes or no."
    if st == STATE_DOC_ALL_Q:
        return "Do you have all of these documents? Say yes or no."
    if st == STATE_DOC_WHICH:
        return "Which document is missing? For example, say income certificate."
    if st == STATE_DOC_MORE_Q:
        return "Is any other document missing? Say yes or no."
    if st == STATE_APPLY_Q:
        return "Do you want the steps to apply? Say yes or no."
    if st == STATE_OTHER_Q:
        return "Would you like to hear other schemes or internships? Say yes or no."
    return "You can say schemes, internships, or start over."


def ask_next_profile_question(hi, prefix=""):
    """Ask for the first missing profile field. Returns a response, or None if the profile is complete."""
    s = sess(hi)
    if s.get("gender") is None:
        s["state"] = STATE_ASK_GENDER
        return respond(hi, prefix + Q_GENDER)
    if s.get("age") is None:
        s["state"] = STATE_ASK_AGE
        return respond(hi, prefix + Q_AGE)
    if s.get("income") is None:
        s["state"] = STATE_ASK_INCOME
        return respond(hi, prefix + Q_INCOME)
    return None


def profile_done(hi, prefix=""):
    """Called after a profile field changes: ask the next question, or summarise results."""
    s = sess(hi)
    r = ask_next_profile_question(hi, prefix)
    if r is not None:
        return r
    pending = s.pop("pending", None)
    if pending and pending.get("type") == "category":
        return list_category(hi, pending["value"], 0, prefix + summary_line(s) + " ")
    if pending and pending.get("type") == "select":
        return select_opportunity(hi, pending["value"], prefix + "Thanks. ")
    s["state"] = STATE_ASK_CATEGORY
    return respond(hi, prefix + summary_line(s) + " " + Q_CATEGORY)


def summary_line(s):
    u = user_of(s)
    n_s = len(matches_for(u, "scheme"))
    n_i = len(matches_for(u, "internship"))
    return ("For age {}, with a family income of {}, you may qualify for {} {} and {} {}.".format(
        u["age"], speak_inr(u["income"]),
        n_s, "government scheme or scholarship" if n_s == 1 else "government schemes and scholarships",
        n_i, "internship" if n_i == 1 else "internships"))


def list_category(hi, kind, offset=0, prefix=""):
    s = sess(hi)
    ids = matches_for(user_of(s), kind)
    s["kind"] = kind
    s["list"] = ids
    if not ids:
        other = "internship" if kind == "scheme" else "scheme"
        s["state"] = STATE_ASK_CATEGORY
        return respond(hi, prefix + "I didn't find {} for your answers. You can say {}, or say start over.".format(
            KIND_WORD[kind], "internships" if other == "internship" else "schemes"))
    if offset >= len(ids):
        offset = 0
    page = ids[offset:offset + PAGE]
    s["offset"] = offset
    s["state"] = STATE_LIST
    lines = []
    for i, oid in enumerate(page, start=offset + 1):
        st, _ = evaluate(OPP_BY_ID[oid], user_of(s))
        tag = "looks eligible" if st == "eligible" else "check the conditions"
        lines.append("Number {}, {}, {}.".format(i, OPP_BY_ID[oid]["say"], tag))
    intro = "Here are the {} for you. ".format(KIND_WORD[kind]) if offset == 0 else ""
    more = offset + PAGE < len(ids)
    if more:
        tail = " Say a number to hear its documents, or say next to hear more."
    else:
        other = "internships" if kind == "scheme" else "schemes"
        tail = " Say a number to hear its documents, or say {}.".format(other)
    card_body = "\n".join("{}. {}".format(i, OPP_BY_ID[o]["title"]) for i, o in enumerate(ids, 1))
    return respond(hi, prefix + intro + " ".join(lines) + tail,
                   reprompt="Say a number from 1 to {}.".format(len(ids)) + (" Or say next." if more else ""),
                   card=("Your " + KIND_WORD[kind], card_body))


def detail_card(opp, user):
    st, res = evaluate(opp, user)
    verdict = {"eligible": "Looks eligible", "check": "Check the conditions", "not": "Probably not eligible"}[st]
    lines = [verdict, "", "What you get: " + opp["benefit"], ""]
    if opp["confirm"]:
        lines.append("Also confirm:")
        lines += ["- " + c for c in opp["confirm"]]
        lines.append("")
    lines.append("Required documents:")
    lines += ["{}. {}".format(i, DOCS[d][0]) for i, d in enumerate(opp["documents"], 1)]
    lines += ["", "Official link: " + opp["url"],
              "Rules checked {}. Confirm on the official site. Opportunity One never applies for you.".format(CHECKED_ON)]
    return (opp["title"], "\n".join(lines))


def documents_speech(opp):
    names = [DOCS[d][1] for d in opp["documents"]]
    n = len(names)
    if n == 1:
        return "For this, you need just one document: {}. Do you have it?".format(names[0])
    return "For this, you need {} documents: {}. Do you have all of them?".format(n, join_words(names))


def select_opportunity(hi, oid, prefix=""):
    s = sess(hi)
    opp = OPP_BY_ID.get(oid)
    if not opp:
        return respond(hi, prefix + "Sorry, I couldn't find that one. " + current_question(s))
    s["opp"] = oid
    s["missing"] = []
    u = user_of(s)
    st, res = evaluate(opp, u)
    if st == "not":
        reasons = [why for _, state, why in res if state == FAIL]
        s["state"] = STATE_NOTELIG_Q
        return respond(hi, prefix + "For {}, you are probably not eligible, because {}. "
                       "Do you still want to hear the documents?".format(opp["say"], join_words(reasons)),
                       card=detail_card(opp, u))
    if st == "eligible":
        verdict = "Based on your answers, you look eligible for {}. ".format(opp["say"])
    else:
        notes = [why for _, state, why in res if state == MAYBE and why]
        verdict = "You may be eligible for {}. ".format(opp["say"])
        if notes:
            verdict += "Note: " + join_words(notes) + ". "
    speech = (prefix + verdict + opp["say_benefit"] + " "
              + ("Please also confirm that {}. ".format(opp["say_confirm"]) if opp.get("say_confirm") else "")
              + documents_speech(opp))
    s["state"] = STATE_DOC_ALL_Q
    return respond(hi, speech, card=detail_card(opp, u))


def resolve_doc_for(opp, doc_id):
    """Map a named document to the one on this opportunity's list when they are related."""
    if not opp or doc_id in opp["documents"]:
        return doc_id
    for alt in DOC_EQUIV.get(doc_id, []):
        if alt in opp["documents"]:
            return alt
    return doc_id


def explain_missing(hi, doc_id):
    s = sess(hi)
    opp = OPP_BY_ID.get(s.get("opp"))
    doc_id = resolve_doc_for(opp, doc_id)
    name, say_name, how, say_how = DOCS[doc_id]
    note = ""
    if opp and doc_id not in opp["documents"]:
        note = "That one isn't on the list for {}, but here is how to get it. ".format(opp["say"])
    elif opp:
        missing = s.get("missing", [])
        if doc_id not in missing:
            missing.append(doc_id)
        s["missing"] = missing
    s["state"] = STATE_DOC_MORE_Q if opp else STATE_OTHER_Q
    follow = "Is any other document missing?" if opp else "Would you like to hear schemes or internships?"
    return respond(hi, note + say_how + " " + follow, card=("How to get: " + name, how))


def missing_summary(s):
    missing = s.get("missing", [])
    if not missing:
        return "Great, you have everything you need. "
    names = [DOCS[d][1] for d in missing]
    return "So, you still need {}. Once you have {}, you can apply. ".format(
        join_words(names), "it" if len(names) == 1 else "them")


def apply_steps(hi, oid):
    s = sess(hi)
    opp = OPP_BY_ID[oid]
    s["opp"] = oid
    s["state"] = STATE_OTHER_Q
    body = "\n".join("{}. {}".format(i, a) for i, a in enumerate(opp["apply"], 1)) + "\n\nOfficial link: " + opp["url"]
    link_say = ("The official website is {}. ".format(opp["say_url"]) if not opp.get("sample") else "")
    return respond(hi, "To apply for {}: {} {}I've sent the details to your Alexa app. "
                   "Opportunity One never applies on your behalf. "
                   "Would you like to hear other schemes or internships?".format(opp["say"], opp["say_apply"], link_say),
                   card=("How to apply: " + opp["title"], body))

# =============================================================================
# Slot reading
# =============================================================================


def _norm(text):
    return re.sub(r"[^a-z0-9' ]", " ", (text or "").lower()).strip()


def _local_resolve(type_name, raw):
    raw_n = " ".join(_norm(raw).split())
    if not raw_n:
        return None
    best = None
    for vid, words in SLOT_TYPES[type_name].items():
        for w in words:
            if raw_n == w:
                return vid
            if best is None and (raw_n in w or w in raw_n) and len(w) > 3:
                best = vid
    return best


def get_slot(hi, name):
    req = hi.request_envelope.request
    intent = getattr(req, "intent", None)
    if not intent or not intent.slots:
        return None
    return intent.slots.get(name)


def slot_value(hi, name):
    slot = get_slot(hi, name)
    if slot is None or slot.value in (None, "", "?"):
        return None
    return slot.value


def slot_id(hi, name, type_name):
    """Entity-resolved id for a custom slot, falling back to local synonym matching."""
    slot = get_slot(hi, name)
    if slot is None:
        return None
    try:
        rpa = slot.resolutions.resolutions_per_authority if slot.resolutions else None
        for auth in rpa or []:
            code = getattr(auth.status.code, "value", auth.status.code)
            if code == "ER_SUCCESS_MATCH" and auth.values:
                v = auth.values[0].value
                vid = v.id or v.name
                if vid in SLOT_TYPES[type_name]:
                    return vid
                local = _local_resolve(type_name, v.name)
                if local:
                    return local
    except AttributeError:
        pass
    return _local_resolve(type_name, slot.value)


def to_number(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def income_from(amount, decimal=None, unit=None):
    """Turn spoken parts into rupees. Returns int or None if unclear."""
    amt = to_number(amount)
    if amt is None or amt < 0:
        return None
    if decimal and amt == int(amt) and str(decimal).isdigit():
        amt = float("{}.{}".format(int(amt), decimal))
    if unit == "lakh":
        val = amt if amt >= 1000 else amt * 100000
    elif unit == "crore":
        val = amt if amt >= 100000 else amt * 10000000
    elif unit == "thousand":
        val = amt if amt >= 1000 else amt * 1000
    elif unit == "rupees":
        if amt != 0 and amt < 1000:
            return None
        val = amt
    else:
        if amt < 100:          # "three" or "two point five" -> lakh
            val = amt * 100000
        elif amt < 1000:       # "four fifty" is ambiguous
            return None
        else:
            val = amt
    if val > 1000000000:
        return None
    return int(round(val))

# =============================================================================
# Handlers
# =============================================================================
sb = SkillBuilder()


@sb.request_handler(can_handle_func=is_request_type("LaunchRequest"))
def launch_handler(hi):
    s = sess(hi)
    s.clear()
    s["state"] = STATE_ASK_GENDER
    return respond(hi, "Welcome to Opportunity One. I'll find government schemes and internships for you "
                       "with three quick questions, and tell you the documents you need. " + Q_GENDER)


@sb.request_handler(can_handle_func=is_intent_name("GenderIntent"))
def gender_handler(hi):
    s = sess(hi)
    g = slot_id(hi, "gender", "GenderType")
    if not g:
        s["state"] = STATE_ASK_GENDER if not profile_complete(s) else s.get("state")
        return respond(hi, "Sorry, I didn't catch that. " + Q_GENDER)
    updating = profile_complete(s)
    s["gender"] = g
    return profile_done(hi, "Updated. " if updating else "Got it. ")


@sb.request_handler(can_handle_func=is_intent_name("IncomeIntent"))
def income_handler(hi):
    s = sess(hi)
    inc = income_from(slot_value(hi, "amount"), slot_value(hi, "decimal"),
                      slot_id(hi, "unit", "IncomeUnitType") if slot_value(hi, "unit") else None)
    if inc is None:
        s["state"] = STATE_ASK_INCOME
        return respond(hi, "Sorry, I didn't get the amount. " + Q_INCOME)
    updating = profile_complete(s)
    s["income"] = inc
    if updating:
        return profile_done(hi, "Updated. ")
    return profile_done(hi, "Thanks. " if profile_complete(s) else "Thanks, family income {}. ".format(speak_inr(inc)))


@sb.request_handler(can_handle_func=is_intent_name("NumberIntent"))
def number_handler(hi):
    s = sess(hi)
    st = s.get("state")
    raw = slot_value(hi, "number")
    num = to_number(raw)
    if st == STATE_ASK_AGE or (st is None and s.get("gender") is not None and s.get("age") is None):
        if num is None or num != int(num) or not 10 <= num <= 100:
            return respond(hi, "Please say your age as a number between ten and one hundred.", Q_AGE)
        updating = profile_complete(s)
        s["age"] = int(num)
        return profile_done(hi, "Updated. " if updating else "Thanks. ")
    if st == STATE_ASK_INCOME:
        inc = income_from(raw)
        if inc is None:
            return respond(hi, "Please say the yearly amount, like three lakh, or fifty thousand.", Q_INCOME)
        s["income"] = inc
        return profile_done(hi, "Thanks. ")
    if st == STATE_ASK_GENDER:
        return respond(hi, "Please say female, male, or other.", Q_GENDER)
    if not profile_complete(s):
        r = ask_next_profile_question(hi, "First, a quick question. ")
        return r
    ids = s.get("list") or []
    if not ids:
        s["state"] = STATE_ASK_CATEGORY
        return respond(hi, "First tell me what to list. " + Q_CATEGORY)
    if num is None or num != int(num) or not 1 <= num <= len(ids):
        return respond(hi, "Please say a number from 1 to {}.".format(len(ids)),
                       "Say a number from 1 to {}.".format(len(ids)))
    return select_opportunity(hi, ids[int(num) - 1])


@sb.request_handler(can_handle_func=is_intent_name("CategoryIntent"))
def category_handler(hi):
    s = sess(hi)
    kind = slot_id(hi, "category", "CategoryType")
    if not kind:
        if profile_complete(s):
            s["state"] = STATE_ASK_CATEGORY
        return respond(hi, "Sorry, " + Q_CATEGORY.lower())
    if not profile_complete(s):
        s["pending"] = {"type": "category", "value": kind}
        return ask_next_profile_question(hi, "Sure. First, three quick questions. ")
    return list_category(hi, kind, 0)


@sb.request_handler(can_handle_func=lambda hi: is_intent_name("MoreIntent")(hi) or is_intent_name("AMAZON.NextIntent")(hi))
def more_handler(hi):
    s = sess(hi)
    if s.get("state") != STATE_LIST or not s.get("kind"):
        if not profile_complete(s):
            return ask_next_profile_question(hi)
        s["state"] = STATE_ASK_CATEGORY
        return respond(hi, Q_CATEGORY)
    offset = s.get("offset", 0) + PAGE
    if offset >= len(s.get("list") or []):
        other = "internships" if s["kind"] == "scheme" else "schemes"
        return respond(hi, "That's the whole list. Say a number to choose one, or say {}.".format(other))
    return list_category(hi, s["kind"], offset)


@sb.request_handler(can_handle_func=is_intent_name("SelectIntent"))
def select_handler(hi):
    s = sess(hi)
    oid = slot_id(hi, "opportunity", "OpportunityType")
    if not oid:
        return respond(hi, "Sorry, I didn't catch which one. You can say its number or its name. " + current_question(s))
    if not profile_complete(s):
        s["pending"] = {"type": "select", "value": oid}
        return ask_next_profile_question(hi, "Sure. To check your eligibility, I need three quick answers. ")
    return select_opportunity(hi, oid)


@sb.request_handler(can_handle_func=is_intent_name("DocumentsIntent"))
def documents_handler(hi):
    s = sess(hi)
    opp = OPP_BY_ID.get(s.get("opp"))
    if not opp:
        if not profile_complete(s):
            return ask_next_profile_question(hi, "First, let's find what suits you. ")
        return respond(hi, "First choose a scheme or internship. " + (
            "Say a number from the list." if s.get("list") else Q_CATEGORY))
    s["state"] = STATE_DOC_ALL_Q
    s["missing"] = []
    return respond(hi, documents_speech(opp), card=detail_card(opp, user_of(s)) if profile_complete(s) else None)


@sb.request_handler(can_handle_func=is_intent_name("MissingDocIntent"))
def missing_doc_handler(hi):
    s = sess(hi)
    doc = slot_id(hi, "document", "DocumentType")
    if not doc:
        opp = OPP_BY_ID.get(s.get("opp"))
        s["state"] = STATE_DOC_WHICH
        if opp:
            names = [DOCS[d][1] for d in opp["documents"]]
            return respond(hi, "Which one is missing? The documents are {}.".format(join_words(names, "or")))
        return respond(hi, "Which document? For example, say income certificate.")
    return explain_missing(hi, doc)


@sb.request_handler(can_handle_func=is_intent_name("HaveAllIntent"))
def have_all_handler(hi):
    s = sess(hi)
    if not s.get("opp"):
        return respond(hi, "Okay. " + current_question(s))
    s["state"] = STATE_APPLY_Q
    return respond(hi, missing_summary(s) + "Do you want the steps to apply?")


@sb.request_handler(can_handle_func=is_intent_name("ApplyIntent"))
def apply_handler(hi):
    s = sess(hi)
    oid = slot_id(hi, "opportunity", "OpportunityType") if slot_value(hi, "opportunity") else None
    oid = oid or s.get("opp")
    if not oid:
        return respond(hi, "Which one do you want to apply for? Say its name, or first say schemes or internships.",
                       "Say the name of a scheme or internship.")
    return apply_steps(hi, oid)


@sb.request_handler(can_handle_func=is_intent_name("WhyNotIntent"))
def why_not_handler(hi):
    s = sess(hi)
    if not profile_complete(s):
        return ask_next_profile_question(hi, "First I need your answers. ")
    rows = not_eligible(user_of(s))
    if not rows:
        return respond(hi, "Good news. Based on your answers, nothing on my list is ruled out. " + current_question(s))
    parts = ["{}, because {}".format(o["say"], join_words(r)) for o, r in rows[:5]]
    more = " and {} more".format(len(rows) - 5) if len(rows) > 5 else ""
    body = "\n".join("- {}: {}".format(o["title"], "; ".join(r)) for o, r in rows)
    s["state"] = STATE_ASK_CATEGORY
    return respond(hi, "You are probably not eligible for {}{}. You can say start over to change your answers, "
                       "or say schemes or internships.".format("; ".join(parts), more),
                   reprompt=Q_CATEGORY, card=("Not eligible, and why", body))


@sb.request_handler(can_handle_func=is_intent_name("RestartIntent"))
def restart_handler(hi):
    s = sess(hi)
    s.clear()
    s["state"] = STATE_ASK_GENDER
    return respond(hi, "Okay, let's start over. " + Q_GENDER)


@sb.request_handler(can_handle_func=is_intent_name("AMAZON.YesIntent"))
def yes_handler(hi):
    s = sess(hi)
    st = s.get("state")
    opp = OPP_BY_ID.get(s.get("opp"))
    if st == STATE_NOTELIG_Q and opp:
        s["state"] = STATE_DOC_ALL_Q
        s["missing"] = []
        return respond(hi, documents_speech(opp))
    if st == STATE_DOC_ALL_Q:
        s["missing"] = []
        s["state"] = STATE_APPLY_Q
        return respond(hi, "Great, you have everything you need. Do you want the steps to apply?")
    if st == STATE_DOC_MORE_Q:
        s["state"] = STATE_DOC_WHICH
        return respond(hi, "Which one?", "Which document is missing? For example, say income certificate.")
    if st == STATE_APPLY_Q and opp:
        return apply_steps(hi, opp["id"])
    if st == STATE_OTHER_Q:
        s["state"] = STATE_ASK_CATEGORY
        return respond(hi, Q_CATEGORY)
    if st == STATE_LIST:
        return more_handler(hi)
    return respond(hi, current_question(s))


@sb.request_handler(can_handle_func=is_intent_name("AMAZON.NoIntent"))
def no_handler(hi):
    s = sess(hi)
    st = s.get("state")
    if st == STATE_NOTELIG_Q:
        s["state"] = STATE_ASK_CATEGORY
        return respond(hi, "Okay. " + Q_CATEGORY + " Or say start over.")
    if st == STATE_DOC_ALL_Q:
        s["state"] = STATE_DOC_WHICH
        return respond(hi, "No problem. Which document is missing? For example, say income certificate.")
    if st in (STATE_DOC_MORE_Q, STATE_DOC_WHICH):
        s["state"] = STATE_APPLY_Q
        return respond(hi, missing_summary(s) + "Do you want the steps to apply?")
    if st == STATE_APPLY_Q:
        s["state"] = STATE_OTHER_Q
        return respond(hi, "Okay. Would you like to hear other schemes or internships?")
    if st in (STATE_OTHER_Q, STATE_ASK_CATEGORY):
        return respond(hi, "Okay. All the best with your applications. Goodbye!", end=True)
    if st == STATE_LIST:
        return respond(hi, "Okay. Say a number to choose one, or say stop.")
    return respond(hi, current_question(s))


@sb.request_handler(can_handle_func=is_intent_name("AMAZON.RepeatIntent"))
def repeat_handler(hi):
    s = sess(hi)
    return respond(hi, s.get("last") or current_question(s), s.get("last_reprompt"))


@sb.request_handler(can_handle_func=is_intent_name("AMAZON.HelpIntent"))
def help_handler(hi):
    s = sess(hi)
    st = s.get("state")
    if st in (STATE_ASK_GENDER, STATE_ASK_AGE, STATE_ASK_INCOME) or not profile_complete(s):
        txt = ("I ask three questions, your gender, age and family income, and then tell you which "
               "government schemes and internships you may qualify for. ")
    elif st == STATE_LIST:
        txt = "Say a number to hear that option's documents, say next for more, or say schemes or internships. "
    elif st in (STATE_DOC_ALL_Q, STATE_DOC_WHICH, STATE_DOC_MORE_Q):
        txt = ("Tell me any document you don't have, for example, I don't have income certificate, and I'll tell you "
               "how to get it. Or say I have all of them. ")
    else:
        txt = ("You can say schemes, internships, a number from the list, how do I apply, "
               "why am I not eligible, or start over. ")
    return respond(hi, txt + current_question(s))


@sb.request_handler(can_handle_func=lambda hi: is_intent_name("AMAZON.CancelIntent")(hi)
                    or is_intent_name("AMAZON.StopIntent")(hi) or is_intent_name("AMAZON.NavigateHomeIntent")(hi))
def stop_handler(hi):
    return respond(hi, "All the best with your applications. Goodbye!", end=True)


@sb.request_handler(can_handle_func=is_intent_name("AMAZON.FallbackIntent"))
def fallback_handler(hi):
    s = sess(hi)
    st = s.get("state")
    if st == STATE_ASK_GENDER:
        txt = "Sorry, please say female, male, or other."
    elif st == STATE_ASK_AGE:
        txt = "Sorry, please say your age as a number, like twenty one."
    elif st == STATE_ASK_INCOME:
        txt = "Sorry, please say the yearly amount, like three lakh, or fifty thousand."
    elif st == STATE_DOC_WHICH:
        opp = OPP_BY_ID.get(s.get("opp"))
        names = [DOCS[d][1] for d in opp["documents"]] if opp else []
        txt = "Sorry, I didn't catch the document. " + (
            "It can be {}.".format(join_words(names, "or")) if names else "For example, say income certificate.")
    else:
        txt = "Sorry, I didn't understand. " + current_question(s)
        return respond(hi, txt)
    return respond(hi, txt, current_question(s))


@sb.request_handler(can_handle_func=is_request_type("SessionEndedRequest"))
def session_ended_handler(hi):
    return hi.response_builder.response


@sb.request_handler(can_handle_func=lambda hi: is_request_type("IntentRequest")(hi))
def unknown_intent_handler(hi):
    """Any intent not handled above (e.g. left over in the model)."""
    return respond(hi, "Sorry, I can't help with that here. " + current_question(sess(hi)))


class CatchAllExceptionHandler(AbstractExceptionHandler):
    def can_handle(self, handler_input, exception):
        return True

    def handle(self, handler_input, exception):
        logger.error(exception, exc_info=True)
        try:
            q = current_question(sess(handler_input))
        except Exception:
            q = "Please say that again."
        return (handler_input.response_builder
                .speak("Sorry, I had trouble with that. " + q)
                .ask(q)
                .response)


sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()
