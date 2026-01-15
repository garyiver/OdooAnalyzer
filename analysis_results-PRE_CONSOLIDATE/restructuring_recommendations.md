# CSL Core Restructuring Recommendations

## Executive Summary

- **Total modules to consolidate**: 15
- **Total fields to move**: 1215
- **Modules that will need updates**: 4
- **Circular dependencies found**: 0

## Priority Order for Migration

1. **csl_project_repair**
2. **csl_rma**
3. **csl_account**
4. **csl_contacts**
5. **csl_photos**
6. **csl_competitor**
7. **csl_timesheet**
8. **csl_sale**
9. **csl_attendance**
10. **csl_website**
11. **csl_purchase**
12. **csl_product**
13. **project_repair_workflow_trigger**
14. **project_repair_workflow**
15. **csl_custom**

## Detailed Module Analysis

### csl_account

- **Field Count**: 76
- **Extending Modules**: 
- **Reasons to Move**:
  - Contains 76 fields

### csl_purchase

- **Field Count**: 11
- **Extending Modules**: 
- **Reasons to Move**:
  - Contains 11 fields

### csl_custom

- **Field Count**: 13
- **Extending Modules**: csl_project_repair, csl_invoice, csl_rma
- **Reasons to Move**:
  - Extended by 3 modules: csl_project_repair, csl_invoice, csl_rma
  - Contains 13 fields

### csl_attendance

- **Field Count**: 17
- **Extending Modules**: 
- **Reasons to Move**:
  - Contains 17 fields

### csl_contacts

- **Field Count**: 66
- **Extending Modules**: 
- **Reasons to Move**:
  - Contains 66 fields

### csl_product

- **Field Count**: 257
- **Extending Modules**: csl_project_repair
- **Reasons to Move**:
  - Contains 257 fields
  - 9 fields used across multiple modules

### csl_rma

- **Field Count**: 173
- **Extending Modules**: 
- **Reasons to Move**:
  - Contains 173 fields

### csl_website

- **Field Count**: 15
- **Extending Modules**: 
- **Reasons to Move**:
  - Contains 15 fields

### csl_project_repair

- **Field Count**: 366
- **Extending Modules**: 
- **Reasons to Move**:
  - Contains 366 fields
  - 10 fields used across multiple modules

### csl_competitor

- **Field Count**: 45
- **Extending Modules**: 
- **Reasons to Move**:
  - Contains 45 fields

### csl_photos

- **Field Count**: 53
- **Extending Modules**: 
- **Reasons to Move**:
  - Contains 53 fields

### csl_sale

- **Field Count**: 26
- **Extending Modules**: 
- **Reasons to Move**:
  - Contains 26 fields

### csl_timesheet

- **Field Count**: 30
- **Extending Modules**: 
- **Reasons to Move**:
  - Contains 30 fields

### project_repair_workflow

- **Field Count**: 48
- **Extending Modules**: csl_project_repair, csl_rma
- **Reasons to Move**:
  - Extended by 2 modules: csl_project_repair, csl_rma
  - Contains 48 fields
  - 17 fields used across multiple modules

### project_repair_workflow_trigger

- **Field Count**: 19
- **Extending Modules**: project_repair_workflow
- **Reasons to Move**:
  - Contains 19 fields

## Modules Requiring Updates

- **csl_invoice**: Will need to depend on `csl_core` (currently depends on: csl_custom)
- **csl_project_repair**: Will need to depend on `csl_core` (currently depends on: csl_custom, csl_product, project_repair_workflow)
- **csl_rma**: Will need to depend on `csl_core` (currently depends on: csl_custom, project_repair_workflow)
- **project_repair_workflow**: Will need to depend on `csl_core` (currently depends on: project_repair_workflow_trigger)
