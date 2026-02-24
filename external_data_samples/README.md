# External Data Sample Files

This directory contains example CSV files showing the expected format for importing company procurement data into AEGIS.

## Quick Start

1. **Copy the sample files** to a working directory:
   ```powershell
   Copy-Item -Recurse external_data_samples\* .\my_company_data\
   ```

2. **Edit the CSV files** with your company data (see `EXTERNAL_DATA_GUIDE.md` for specifications)

3. **Run the import**:
   ```powershell
   python data_ingestion\external_data_loader.py --input-dir .\my_company_data
   ```

4. **Populate warehouse & run analytics**:
   ```powershell
   python data_ingestion\populate_warehouse.py
   python run_aegis_pipeline.py
   ```

5. **Launch dashboard**:
   ```powershell
   streamlit run streamlit_app.py
   ```

## Files

| File | Required | Rows | Description |
|------|----------|------|-------------|
| suppliers.csv | Yes | 10 | Supplier master data with country, currency, lead times |
| materials.csv | Yes | 12 | Material catalog with categories and standard costs |
| purchase_orders.csv | Yes | 12 | PO headers with dates, amounts, and status |
| po_line_items.csv | Yes | 21 | PO line items linking POs to materials |
| shipments.csv | No | 12 | Shipment tracking with transport modes and dates |
| invoices.csv | No | 12 | Invoice data with payment dates and status |
| esg_assessments.csv | No | 10 | ESG scores (env/social/governance) per supplier |

## Notes

- Country and currency values must match the AEGIS reference tables (see `database/09_seed_reference_data.sql`)
- Supplier names must be consistent across all files (case-sensitive)
- Dates use ISO 8601 format: `YYYY-MM-DD`
- See `EXTERNAL_DATA_GUIDE.md` for full column specifications and validation rules
