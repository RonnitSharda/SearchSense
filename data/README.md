# data/

`myntra_fashion_products.csv.gz` is an unmodified gzip of `Myntra_fashion_products.csv` from the Kaggle
dataset `nirokey/myntra-fashion-products` (12,491 rows). Load with `pandas.read_csv(path)`; compression is inferred.
Fetch it again with `kagglehub.dataset_download("nirokey/myntra-fashion-products")` (works without a Kaggle login).

Columns: `name, sku, mpn, price (INR, int), in_stock (bool), currency, brand, description, images (URL), gender`.
Gender values: Women 5126, Men 4591, Unisex 1188, Boys 1100, Girls 440, Unisex Kids 46.
There are no ratings, sizes, MRP/discount, colour or fabric columns: derive colour/fabric/type/style from `name` and
`description`, and treat any rating, size or fit data as simulated.
