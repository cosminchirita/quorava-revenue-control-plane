# Power BI integration

1. Start Quorava locally and confirm `http://127.0.0.1:8787/api/health` returns `status: ok`.
2. In Power BI Desktop, create a blank query and paste `powerbi/power-query.m` into Advanced Editor.
3. Set the query name to `RevenueFacts` and apply types.
4. Add the measures from `powerbi/measures.dax` to a dedicated measures table.
5. Import `powerbi/theme.json` from **View → Themes → Browse for themes**.
6. Reconcile `[Net Revenue EUR]` to the Quorava overview before publishing.

For a static import, use `data/warehouse/powerbi_revenue_facts.csv` after running the pipeline. The API and file contain the same canonical grain.

Production deployments should use an authenticated gateway, managed credentials, refresh monitoring, row-level security and certified semantic models.

