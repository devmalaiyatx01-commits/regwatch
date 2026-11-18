# Classifier evaluation

## Rule classifier, test split (49 labelled publications)

| Metric | Value |
|---|---:|
| Category accuracy | 85.7% |
| Category macro-F1 | 0.817 |
| Severity accuracy | 91.8% |
| Recall on high-severity items | 100.0% |

| Language | Category accuracy | Items |
|---|---:|---:|
| en | 84.8% | 33 |
| es | 87.5% | 8 |
| ja | 87.5% | 8 |

| Category | F1 |
|---|---:|
| recall | 0.86 |
| safety_alert | 0.91 |
| enforcement | 0.75 |
| guidance | 1.00 |
| approval | 0.50 |
| other | 0.88 |

Misses (title / gold category / predicted / gold severity / predicted):

- Surrender of Cosmetic Registration Certificate No. RC/COS-005067 dated 05.07.2024 : other -> approval, low -> low
- Drug Regulatory and Law Enforcement Agencies Intensify Coordinated Action Against Illegal  : enforcement -> other, medium -> low
- Manufacturing and marketing of un-approved drug products containing Enclomiphene and its c : enforcement -> approval, medium -> low
- Surrender of cosmetic Registration Certificate No. RC/COS-003938 dated 23.08.2023 : other -> approval, low -> low
- Reunión del Comité de Medicamentos de Uso Humano de noviembre de 2026 : approval -> safety_alert, low -> low
- Nova Biomedical StatStrip ketone test strips: risk of disruption to blood ketone testing d : safety_alert -> recall, medium -> medium
- GLP-1 receptor agonists and dual GLP-1/GIP receptor agonists: strengthened warnings on acu : safety_alert -> safety_alert, medium -> high
- [PMDA]医療従事者からの副反応疑い報告、副作用・感染症・不具合報告及び疾病等報告のファクシミリによる受付の一時停止について[401KB]（2026年4月22日） : other -> safety_alert, low -> medium

## Rule classifier, dev split (75 labelled publications)

| Metric | Value |
|---|---:|
| Category accuracy | 90.7% |
| Category macro-F1 | 0.913 |
| Severity accuracy | 89.3% |
| Recall on high-severity items | 100.0% |

| Language | Category accuracy | Items |
|---|---:|---:|
| en | 90.6% | 53 |
| es | 77.8% | 9 |
| fr | 100.0% | 4 |
| ja | 100.0% | 9 |

| Category | F1 |
|---|---:|
| recall | 0.96 |
| safety_alert | 0.92 |
| supply | 1.00 |
| enforcement | 1.00 |
| guidance | 0.80 |
| approval | 0.80 |
| other | 0.91 |

Misses (title / gold category / predicted / gold severity / predicted):

- Digital Monitoring System on the ONDLS portal for monitoring the supply chain of high-risk : guidance -> safety_alert, medium -> medium
- La AEMPS publica unas recomendaciones para favorecer la correcta utilización de productos  : guidance -> other, medium -> low
- Los problemas de suministro de impacto mayor descienden por debajo del 0,20% por primera v : supply -> supply, low -> medium
- La AEMPS informa de casos de resistencia a algunos antibióticos empleados para tratar el i : safety_alert -> other, medium -> low
- Meeting highlights from the Committee for Medicinal Products for Human Use (CHMP) 9-12 Nov : approval -> guidance, low -> low
- Meeting highlights from the Committee for Veterinary Medicinal Products (CVMP) 3-5 Novembe : approval -> other, low -> low
- Meeting highlights from the Pharmacovigilance Risk Assessment Committee (PRAC) 26 - 29 Oct : safety_alert -> safety_alert, medium -> low
- Medline - Beds, Rails, Mattresses, and accessories : recall -> safety_alert, medium -> medium
- Filters should be used during the administration of Parenteral Nutrition for patients in a : safety_alert -> safety_alert, medium -> high
- Botulinum toxin type A products: updated warnings regarding risk of iatrogenic botulism : safety_alert -> safety_alert, medium -> high
- Amiodarone: reminder of risks of treatment and need for patient monitoring and supervision : safety_alert -> safety_alert, medium -> high
- [SHINSA]The information of New Drug Review with Electronic Data updated : guidance -> other, medium -> low
