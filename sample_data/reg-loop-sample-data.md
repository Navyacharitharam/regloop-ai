# Sample Document 1: Regulatory Update

## File Name

`DORA_ICT_Risk_Update_2026.pdf`

## Purpose

External regulation document uploaded by the user.

Contains 7 obligations.

---

### Excerpt

### ICT Risk Governance Requirements

Financial entities shall maintain documented ICT risk management procedures.

The procedures shall:

* identify critical ICT systems;
* define ownership responsibilities;
* establish annual risk reviews;
* maintain evidence of risk assessments;
* document incident escalation procedures.

### Third-Party ICT Providers

Financial entities shall:

* review critical ICT vendors at least annually;
* maintain evidence of vendor assessments;
* define responsible owners for vendor oversight;
* establish escalation procedures for unresolved vendor risks.

### Incident Management

Financial entities shall:

* maintain documented incident response procedures;
* conduct annual incident-response testing;
* preserve evidence of testing activities;
* document post-incident reviews.

---

### Expected Obligations Extracted

| ID  | Obligation                                         |
| --- | -------------------------------------------------- |
| O1  | Maintain documented ICT risk management procedures |
| O2  | Identify critical ICT systems                      |
| O3  | Define ownership responsibilities                  |
| O4  | Conduct annual ICT risk reviews                    |
| O5  | Maintain evidence of risk assessments              |
| O6  | Document incident escalation procedures            |
| O7  | Review critical ICT vendors annually               |
| O8  | Maintain evidence of vendor assessments            |
| O9  | Define vendor oversight ownership                  |
| O10 | Establish vendor risk escalation procedures        |
| O11 | Maintain documented incident response procedures   |
| O12 | Conduct annual incident-response testing           |
| O13 | Preserve evidence of testing activities            |
| O14 | Document post-incident reviews                     |


---

# Sample Document 2: ICT Risk Policy

## File Name

`ICT_Risk_Policy.pdf`

---

### Excerpt

# ICT Risk Policy

The organization maintains a risk management framework for technology systems.

The ICT Risk Team is responsible for maintaining the framework.

Risk assessments should be conducted periodically.

Documentation should be retained whenever practical.

---

## Intentional Gaps

Missing:

❌ annual review frequency

❌ evidence retention requirements

❌ escalation process

etc.

---

# Sample Document 3: Vendor Risk Policy

## File Name

`Vendor_Risk_Policy.pdf`

---

### Excerpt

# Third Party Vendor Risk Policy

Critical vendors shall be periodically reviewed.

Vendor reviews should consider:

* security posture
* operational resilience
* service availability

Vendor concerns may be escalated when appropriate.

---

## Intentional Gaps

Missing:

❌ annual review cycle

❌ assigned owner

❌ evidence requirements

etc.

---

### Example Gap AI Should Find

Regulation:

> Review critical ICT vendors at least annually

Policy:

> Critical vendors shall be periodically reviewed

Result:

```text
Partially Covered

Gap:
No review frequency defined.
```

---

# Sample Document 4: Incident Response Policy

## File Name

`Incident_Response_Policy.pdf`

---

### Excerpt

# Incident Response Policy

The organization shall maintain an incident response process.

The security team coordinates incident management activities.

Lessons learned may be documented after major incidents.

---

## Intentional Gaps

Missing:

❌ annual testing requirement

❌ evidence retention

❌ mandatory post-incident reviews

etc.

---

# Sample Document 5: Responsibility Matrix

## File Name

`responsibility_matrix.csv`

```csv
Domain,Owner,Department
ICT Risk,Jane Smith,Risk Management
Vendor Risk,Michael Johnson,Procurement
Incident Response,Sarah Lee,Security Operations
Compliance,David Brown,Compliance
Legal,Emily Wilson,Legal
```

---

# Expected Output Dataset (for Reviewers)

Provide a reference JSON file:

`expected_output.json`

```json
{
  "obligations": [
    {
      "id": "O5",
      "obligation": "Review critical ICT vendors annually",
      "mappedPolicy": "Vendor Risk Policy",
      "coverage": "Partially Covered",
      "risk": "Medium",
      "gap": "Review frequency not defined"
    },
    {
      "id": "O6",
      "obligation": "Conduct annual incident-response testing",
      "mappedPolicy": "Incident Response Policy",
      "coverage": "Not Covered",
      "risk": "High",
      "gap": "Testing requirement missing"
    }
  ]
}
```

---

# Sample Policy Pull Request Output

The challenge reviewers should expect something similar to:

```text
Policy Pull Request #001

Regulatory Citation:
DORA ICT Risk Requirement 2.1

Affected Policy:
Vendor Risk Policy

Gap:
Review frequency is not defined.

Current Text:
Critical vendors shall be periodically reviewed.

Proposed Text:
Critical vendors shall be reviewed at least once every 12 months.

Suggested Owner:
Michael Johnson

Risk Level:
Medium

Confidence:
92%
```
