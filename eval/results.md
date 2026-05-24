# RAG Eval Report

- **Total questions:** 12 (9 retrieval, 3 refusal)
- **Retrieval hit-rate@5:** 8/9 = 89%
- **Refusal accuracy:** 3/3 = 100%
- **Mean faithfulness (0-3):** 2.92

| # | Type | Hit | Faith | Question | Retrieved | Expected |
|---|---|---|---|---|---|---|
| 1 | retrieval | ✅ | 3 | What motor milestones should I document at 6 months? | cdc_milestones_all_ages.pdf | cdc_milestones_all_ages.pdf |
| 2 | retrieval | ✅ | 3 | When do most children start to say their first words? | cdc_milestones_all_ages.pdf | cdc_milestones_all_ages.pdf |
| 3 | retrieval | ✅ | 2 | Should a 2-year-old be using two-word phrases? | cdc_milestones_all_ages.pdf, head_start_1302_subpa | cdc_milestones_all_ages.pdf |
| 4 | retrieval | ✅ | 3 | What social-emotional milestones are expected at 4 years? | cdc_milestones_all_ages.pdf | cdc_milestones_all_ages.pdf |
| 5 | retrieval | ✅ | 3 | What are the staff qualification requirements for Head Start | head_start_1302_subpart_B_Program-Structure.txt, h | head_start_1302_subpart_I_Human-Resource |
| 6 | retrieval | ❌ | 3 | What does Head Start require for developmental screening of  | cdc_milestones_all_ages.pdf, head_start_1302_subpa | head_start_1302_subpart_C_Education-and- |
| 7 | retrieval | ✅ | 3 | What family engagement activities are required under Head St | head_start_1302_subpart_E_Family-and-Community-Eng | head_start_1302_subpart_E_Family-and-Com |
| 8 | retrieval | ✅ | 3 | What are the eligibility requirements for Head Start enrollm | head_start_1302_subpart_A_Eligibility-Recruitment- | head_start_1302_subpart_A_Eligibility-Re |
| 9 | retrieval | ✅ | 3 | What transition services must Head Start programs provide? | head_start_1302_subpart_F_Additional-Services-for- | head_start_1302_subpart_G_Transition-Ser |
| 10 | refusal | ✅ | 3 | What is the staff:child ratio for 18-month-olds in Ohio? | head_start_1302_subpart_A_Eligibility-Recruitment- | (refuse) |
| 11 | refusal | ✅ | 3 | What does NAEYC say about outdoor play? | cdc_milestones_all_ages.pdf, head_start_1302_subpa | (refuse) |
| 12 | refusal | ✅ | 3 | How do I file my company's taxes? | cdc_milestones_all_ages.pdf, head_start_1302_subpa | (refuse) |
