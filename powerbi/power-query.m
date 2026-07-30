let
    Source = Csv.Document(
        Web.Contents("http://127.0.0.1:8787/api/powerbi/export.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    TypedColumns = Table.TransformColumnTypes(
        PromotedHeaders,
        {
            {"record_id", type text}, {"order_id", type text},
            {"transaction_date", type date}, {"region", type text},
            {"country", type text}, {"channel", type text},
            {"product_family", type text}, {"gross_eur", Currency.Type},
            {"net_eur", Currency.Type}, {"cost_eur", Currency.Type},
            {"margin_eur", Currency.Type}, {"status", type text},
            {"quality_score", type number}, {"source_type", type text},
            {"lineage_hash", type text}
        },
        "en-GB"
    )
in
    TypedColumns

