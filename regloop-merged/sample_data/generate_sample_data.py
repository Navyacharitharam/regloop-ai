#!/usr/bin/env python3
"""Generate sample data files for RegLoop testing."""
import os

# Try to use reportlab for PDF generation, fall back to fpdf2
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    HAVE_REPORTLAB = True
except ImportError:
    HAVE_REPORTLAB = False

try:
    from fpdf import FPDF
    HAVE_FPDF = True
except ImportError:
    HAVE_FPDF = False

import csv

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

REGULATION_TEXT = """FINANCIAL DATA PROTECTION AND PRIVACY REGULATION 2024
Issued by: Financial Regulatory Authority
Effective Date: January 1, 2025
Document Reference: FRA-DPP-2024-001

SECTION 1: SCOPE AND APPLICABILITY
1.1 This regulation applies to all financial institutions operating within the jurisdiction that collect, process, store, or transmit customer personal and financial data.
1.2 Institutions must designate a Chief Data Protection Officer (CDPO) within 90 days of this regulation taking effect.
1.3 All third-party vendors with access to customer data must be subject to equivalent data protection standards.

SECTION 2: DATA COLLECTION AND CONSENT
2.1 Financial institutions shall obtain explicit, informed consent from customers before collecting personal data beyond what is strictly necessary for the provision of contracted services.
2.2 Consent records must be maintained for a minimum of 7 years and must be producible on regulatory request within 48 hours.
2.3 Customers must be provided with clear opt-out mechanisms for non-essential data processing activities. Opt-out requests must be processed within 5 business days.
2.4 Institutions must provide customers with an annual data usage summary detailing all categories of data collected and their purposes.

SECTION 3: DATA SECURITY AND BREACH RESPONSE
3.1 All customer data at rest must be encrypted using AES-256 or equivalent approved encryption standards.
3.2 Customer data in transit must use TLS 1.3 or higher. Legacy protocols TLS 1.0 and 1.1 are prohibited.
3.3 Multi-factor authentication (MFA) is mandatory for all internal systems accessing customer personal data.
3.4 In the event of a data breach affecting 500 or more customers, the institution must notify the regulatory authority within 72 hours of discovery.
3.5 Breach notifications to affected customers must be issued within 30 days and must include a description of the data compromised, potential risks, and remediation steps taken.
3.6 Institutions must conduct penetration testing on all customer-facing systems at least annually.

SECTION 4: DATA RETENTION AND DELETION
4.1 Customer transaction data must be retained for a minimum of 5 years from the date of the last transaction.
4.2 Inactive customer records (no activity for 7+ years) must be reviewed for deletion or archival in compliance with applicable laws.
4.3 Upon customer request for data deletion, institutions must complete deletion within 30 days, except where retention is required by law.
4.4 Data deletion must be verified and documented through formal data destruction certificates.

SECTION 5: THIRD-PARTY AND VENDOR MANAGEMENT
5.1 All third-party vendors processing customer data must execute a Data Processing Agreement (DPA) with the institution prior to data access.
5.2 Vendor compliance with this regulation must be assessed annually through formal audits or certifications.
5.3 Institutions must maintain a complete and current inventory of all third-party vendors with access to customer data.
5.4 In the event of a vendor breach, the institution retains full accountability for regulatory compliance and must notify the authority as per Section 3.4.

SECTION 6: CUSTOMER RIGHTS
6.1 Customers have the right to access all personal data held by the institution. Requests must be fulfilled within 15 business days.
6.2 Customers may request correction of inaccurate personal data. Corrections must be processed within 10 business days.
6.3 Customers have the right to data portability. Institutions must provide data in a machine-readable format (CSV, JSON) within 20 business days of request.
6.4 Institutions must appoint a dedicated Customer Data Rights team or designated officer to handle all data rights requests.

SECTION 7: GOVERNANCE AND ACCOUNTABILITY
7.1 The board of directors must receive a quarterly data protection compliance report.
7.2 Institutions must maintain an internal data protection register documenting all processing activities, lawful bases, and retention schedules.
7.3 A Data Protection Impact Assessment (DPIA) must be conducted for any new system or process involving large-scale processing of customer personal data.
7.4 Staff with access to customer data must complete annual data protection training. Completion records must be maintained for 3 years.

PENALTIES
Non-compliance with this regulation may result in fines of up to 4% of annual global turnover or $10 million, whichever is greater, per violation."""

POLICY_AML_TEXT = """ACME FINANCIAL SERVICES
CUSTOMER DATA MANAGEMENT POLICY
Version 3.1 | Approved: March 2024
Policy Owner: Chief Compliance Officer

1. PURPOSE AND SCOPE
This policy establishes requirements for the collection, processing, storage, and protection of customer personal and financial data at Acme Financial Services. It applies to all employees, contractors, and systems.

2. DATA GOVERNANCE
2.1 The Chief Compliance Officer (CCO) is responsible for data governance. A Data Privacy Committee meets quarterly to review compliance.
2.2 All new data processing activities require approval from the Data Privacy Committee before implementation.
2.3 An internal data register is maintained and updated semi-annually.

3. DATA COLLECTION
3.1 Customer data is collected only for specified, legitimate business purposes.
3.2 Customer consent is obtained at account opening for standard banking services.
3.3 Marketing communications require separate opt-in consent.

4. DATA SECURITY
4.1 Customer data at rest is encrypted using AES-256 encryption standards.
4.2 All network connections use SSL/TLS encryption. Systems are reviewed annually.
4.3 Access to customer systems requires username and password authentication with session timeouts.
4.4 The IT Security team conducts annual vulnerability assessments.

5. INCIDENT RESPONSE
5.1 The Information Security team is notified of any suspected data breach within 24 hours of discovery.
5.2 A post-incident report is produced within 30 days for all confirmed breaches.
5.3 Customer notification for breaches is handled by the Communications team.

6. DATA RETENTION
6.1 Transaction records are retained for 5 years in accordance with financial regulations.
6.2 Inactive accounts are flagged for review after 5 years.
6.3 Customer requests for data access are processed within 30 business days.

7. THIRD-PARTY VENDORS
7.1 Vendors with access to customer data must sign a standard Non-Disclosure Agreement (NDA).
7.2 Key vendor relationships are reviewed annually during contract renewal.
7.3 A vendor list is maintained by the Procurement team.

8. TRAINING AND AWARENESS
8.1 All staff complete annual compliance training covering data handling basics.
8.2 Training completion is tracked by HR.

9. CUSTOMER RIGHTS
9.1 Customers may request access to their data by contacting Customer Service.
9.2 Data correction requests are processed by the Customer Service team.
9.3 Customers wishing to close accounts may request data deletion."""

POLICY_IT_TEXT = """ACME FINANCIAL SERVICES
INFORMATION TECHNOLOGY SECURITY POLICY
Version 2.5 | Approved: January 2024
Policy Owner: Chief Information Security Officer

1. SCOPE
This policy applies to all information systems, networks, and data assets owned or operated by Acme Financial Services.

2. ACCESS CONTROL
2.1 Access to systems is granted on a least-privilege basis.
2.2 User accounts are reviewed quarterly by department managers.
2.3 Privileged access accounts require manager approval and are reviewed monthly.
2.4 Passwords must meet complexity requirements: minimum 12 characters, mixed case, numbers, and symbols.
2.5 Shared accounts are prohibited except for designated service accounts.

3. ENCRYPTION
3.1 All laptops and mobile devices must use full-disk encryption.
3.2 Customer data stored in databases uses AES-256 encryption.
3.3 Email containing customer PII must be encrypted using approved tools.

4. NETWORK SECURITY
4.1 The network is segmented into security zones. Customer data resides in the restricted zone.
4.2 All external-facing systems are protected by web application firewalls (WAF).
4.3 TLS 1.2 is the minimum standard for all encrypted communications. TLS 1.3 is preferred.
4.4 Legacy protocols (SSL, TLS 1.0) are disabled on production systems.

5. VULNERABILITY MANAGEMENT
5.1 Vulnerability scans are conducted monthly on all systems.
5.2 Critical vulnerabilities are patched within 7 days of discovery.
5.3 Annual penetration testing is conducted by an approved third-party vendor.
5.4 A bug bounty program covers externally-facing digital products.

6. INCIDENT MANAGEMENT
6.1 Security incidents are classified by severity (P1-P4).
6.2 P1 incidents (critical) require immediate escalation to CISO and executive team.
6.3 Incident records are retained for 3 years.
6.4 The CISO reports security posture to the board quarterly.

7. THIRD-PARTY SECURITY
7.1 Third-party vendors must complete a security questionnaire before onboarding.
7.2 Vendors with access to production systems must provide SOC 2 Type II reports.
7.3 Cloud service providers must meet FedRAMP Moderate or equivalent certification.

8. DATA LOSS PREVENTION
8.1 DLP tools monitor outbound data transfers from corporate systems.
8.2 Transfers of customer PII to personal email or storage are blocked and alerted.
8.3 USB devices are disabled on customer-data-processing workstations."""

def write_text_as_pdf(filename: str, title: str, content: str):
    """Write content to a PDF using available library."""
    if HAVE_REPORTLAB:
        doc = SimpleDocTemplate(filename, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        story.append(Paragraph(title, styles['Title']))
        story.append(Spacer(1, 12))
        for para in content.split('\n\n'):
            if para.strip():
                story.append(Paragraph(para.replace('\n', '<br/>'), styles['Normal']))
                story.append(Spacer(1, 6))
        doc.build(story)
        print(f"Created (reportlab): {filename}")
    elif HAVE_FPDF:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=10)
        pdf.set_auto_page_break(auto=True, margin=15)
        for line in content.split('\n'):
            try:
                pdf.cell(0, 5, line[:120], new_x="LMARGIN", new_y="NEXT")
            except:
                pass
        pdf.output(filename)
        print(f"Created (fpdf2): {filename}")
    else:
        # Fallback: write as text file with .pdf extension note
        txt_file = filename.replace('.pdf', '.txt')
        with open(txt_file, 'w') as f:
            f.write(f"{title}\n\n{content}")
        print(f"Note: No PDF library available. Written as text: {txt_file}")
        print("Install reportlab or fpdf2: pip install reportlab fpdf2")


def create_sample_data():
    # Create regulation PDF
    write_text_as_pdf(
        os.path.join(OUTPUT_DIR, "sample_regulation_FRA_DPP_2024.pdf"),
        "Financial Data Protection and Privacy Regulation 2024",
        REGULATION_TEXT
    )

    # Create policy PDFs
    write_text_as_pdf(
        os.path.join(OUTPUT_DIR, "sample_policy_data_management.pdf"),
        "Customer Data Management Policy v3.1",
        POLICY_AML_TEXT
    )

    write_text_as_pdf(
        os.path.join(OUTPUT_DIR, "sample_policy_it_security.pdf"),
        "Information Technology Security Policy v2.5",
        POLICY_IT_TEXT
    )

    # Create responsibility matrix CSV
    matrix_file = os.path.join(OUTPUT_DIR, "sample_responsibility_matrix.csv")
    rows = [
        {"role": "Chief Data Protection Officer", "team": "Compliance", "email": "cdpo@acme.com", "domain": "Data Privacy, Governance"},
        {"role": "Chief Compliance Officer", "team": "Compliance", "email": "cco@acme.com", "domain": "Regulatory Compliance, Governance"},
        {"role": "Chief Information Security Officer", "team": "IT Security", "email": "ciso@acme.com", "domain": "Data Security, Breach Response, IT"},
        {"role": "Head of Data Engineering", "team": "Technology", "email": "data-eng@acme.com", "domain": "Encryption, Data Storage, Retention"},
        {"role": "VP Third-Party Risk", "team": "Risk Management", "email": "tprm@acme.com", "domain": "Vendor Management, Third-Party Risk"},
        {"role": "Head of Customer Operations", "team": "Customer Service", "email": "cust-ops@acme.com", "domain": "Customer Rights, Data Access Requests"},
        {"role": "General Counsel", "team": "Legal", "email": "legal@acme.com", "domain": "Legal Compliance, Contracts, DPAs"},
        {"role": "Director of Internal Audit", "team": "Audit", "email": "audit@acme.com", "domain": "Audit Trail, Reporting, Governance"},
        {"role": "Head of HR", "team": "Human Resources", "email": "hr@acme.com", "domain": "Training, Staff Compliance"},
        {"role": "Head of Procurement", "team": "Procurement", "email": "procurement@acme.com", "domain": "Vendor Onboarding, Contracts"},
    ]
    with open(matrix_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["role", "team", "email", "domain"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Created: {matrix_file}")

    print("\n✅ Sample data created successfully!")
    print("\nFiles created:")
    print("  📄 sample_regulation_FRA_DPP_2024.pdf  → Upload as 'Regulatory Update'")
    print("  📄 sample_policy_data_management.pdf   → Upload as 'Internal Policy'")
    print("  📄 sample_policy_it_security.pdf       → Upload as 'Internal Policy'")
    print("  📄 sample_responsibility_matrix.csv    → Upload as 'Responsibility Matrix'")


if __name__ == "__main__":
    create_sample_data()
