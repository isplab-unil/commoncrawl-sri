from pyspark.shell import sqlContext

# ---------------------------
# --------- DATA ------------
# ---------------------------

# Load the parquet files
sqlContext.read.parquet("*.parquet").registerTempTable("cc")
sqlContext.read.csv('../input/top-1m-cisco.csv').registerTempTable('top1m')


def sql(sql):
    sqlContext \
        .sql(sql) \
        .show(20, False)


def csv(file, sql):
    sqlContext \
        .sql(sql) \
        .repartition(1) \
        .write.format("csv") \
        .option("header", "true") \
        .save(file)


# ---------------------------
# ----- VERIFICATIONS -------
# ---------------------------

csv("count.csv", "SELECT count(*) as count FROM cc")

sqlContext.sql("""
SELECT count(*) FROM cc WHERE error is not NULL 
""").show(20, False)

sqlContext.sql("""
SELECT count(*) FROM cc WHERE has_subresource
""").show(20, False)

sqlContext.sql("""
SELECT subresources.attributes FROM cc WHERE has_subresource
""").show(20, False)

sqlContext.sql("""
SELECT csp FROM cc WHERE csp is not NULL 
""").show(20, False)

sqlContext.sql("""
SELECT cors FROM cc WHERE cors is not NULL 
""").show(20, False)

sqlContext.sql("""
SELECT subresources.crossorigin FROM cc WHERE size(filter(subresources, s -> s.crossorigin IS NOT NULL)) > 0
""").show(100, False)

# ---------------------------
# -------- QUERIES ----------
# ---------------------------

# Q1: What is the number of pages by protocol?

csv("01_pages_per_protocol.csv", """
SELECT 
    if(url LIKE 'https%', 'https', if(url LIKE 'http%', 'http', 'other')) AS protocol, 
    count(*) AS number,
    (SELECT count(*) FROM cc) AS total,
    round(100 * count(*) / (SELECT count(*) FROM cc), 2) AS percentage 
FROM cc 
GROUP BY protocol
""")

# ---------------------------

# Q2: What is the number of pages that include at least one SRI?

csv("02_pages_with_sri.csv", """
SELECT 
    count(*) AS number,
    (SELECT count(*) FROM cc) AS total,
    round(100 * count(*) / (SELECT count(*) FROM cc), 2) AS percentage 
FROM cc 
WHERE size(filter(subresources, s -> s.integrity IS NOT NULL)) > 0
""")

csv("02_pages_with_sri_script.csv", """
SELECT 
    count(*) AS number,
    (SELECT count(*) FROM cc) AS total,
    round(100 * count(*) / (SELECT count(*) FROM cc), 2) AS percentage 
FROM cc 
WHERE size(filter(subresources, s -> s.name == 'script' AND s.integrity IS NOT NULL)) > 0
""")

csv("02_pages_with_sri_link.csv", """
SELECT 
    count(*) AS number,
    (SELECT count(*) FROM cc) AS total,
    round(100 * count(*) / (SELECT count(*) FROM cc), 2) AS percentage 
FROM cc 
WHERE size(filter(subresources, s -> s.name == 'link' AND s.integrity IS NOT NULL)) > 0
""")

# ---------------------------

# Q3: What is the number of pages per number of number SRI?
csv("03_page_per_sri.csv", """
SELECT 
    size(filter(subresources, s -> s.integrity IS NOT NULL)) AS sri, 
    count(*) AS page 
FROM cc 
WHERE size(filter(subresources, s -> s.integrity IS NOT NULL)) > 0 
GROUP BY sri 
ORDER BY sri ASC
""")

csv("03_page_per_sri_script.csv", """
SELECT 
    size(filter(subresources, s -> s.name == 'script' AND s.integrity IS NOT NULL)) AS sri, 
    count(*) AS page 
FROM cc 
WHERE size(filter(subresources, s -> s.name == 'script' AND s.integrity IS NOT NULL)) > 0 
GROUP BY sri 
ORDER BY sri ASC
""")

csv("03_page_per_sri_link.csv", """
SELECT 
    size(filter(subresources, s -> s.name == 'link' AND s.integrity IS NOT NULL)) AS sri, 
    count(*) AS page 
FROM cc 
WHERE size(filter(subresources, s -> s.name == 'link' AND s.integrity IS NOT NULL)) > 0 
GROUP BY sri 
ORDER BY sri ASC
""")

# ---------------------------

# Q4: What is the number of SRI per hash algorithm?

csv("04_sri_per_alg.csv", """
SELECT 
    substring_index(trim(sri.integrity), '-', 1) as alg, 
    count(*) as sri
FROM cc LATERAL VIEW explode(subresources) T AS sri
WHERE size(filter(subresources, s -> s.integrity IS NOT NULL)) > 0
  AND sri.integrity IS NOT NULL
GROUP BY alg
ORDER BY alg
""")

# ---------------------------

# Q5: Are there invalid integrity attributes in the dataset?
sqlContext.sql("""
SELECT
    cc.url,
    sri.target,
    trim(sri.integrity) as integrity,
    length(sri.integrity) as length
FROM cc LATERAL VIEW explode(subresources) T AS sri
WHERE sri.integrity IS NOT NULL
  AND trim(sri.integrity) != ""
  AND length(trim(sri.integrity)) != 219 -- sha256+sha384+sha512
  AND length(trim(sri.integrity)) != 167 -- sha384+sha512
  AND length(trim(sri.integrity)) != 147 -- sha256+sha512
  AND length(trim(sri.integrity)) != 95 -- sha512
  AND length(trim(sri.integrity)) != 71 -- sha384
  AND length(trim(sri.integrity)) != 51 -- sha256
""").show(100, False)

# ---------------------------

# Q6: What is the distribution of SRI per protocol?

sqlContext.sql("""
SELECT if(sri.target LIKE 'https%', 'https', if(sri.target LIKE 'http%', 'http', if(url LIKE 'https%', 'https', 'http'))) AS protocol, count(*) as sri FROM (
    SELECT url, filter(subresources, s -> s.integrity IS NOT NULL) AS subresources 
    FROM cc 
    WHERE size(filter(subresources, s -> s.integrity IS NOT NULL)) > 0
) LATERAL VIEW explode(subresources) T AS sri
GROUP BY protocol
ORDER BY protocol DESC
""").show(20, False)

# ---------------------------

# Q7: What is the number of elements per target protocol?

from urllib.parse import urljoin
from urllib.parse import urlparse

lambdas = [
    ('http_http_l', lambda r: r[0].scheme == 'http' and r[1].scheme == 'http' and r[0].netloc == r[1].netloc),
    ('http_http_r', lambda r: r[0].scheme == 'http' and r[1].scheme == 'http' and r[0].netloc != r[1].netloc),
    ('http_https_l', lambda r: r[0].scheme == 'http' and r[1].scheme == 'https' and r[0].netloc == r[1].netloc),
    ('http_https_r', lambda r: r[0].scheme == 'http' and r[1].scheme == 'https' and r[0].netloc != r[1].netloc),
    ('https_http_l', lambda r: r[0].scheme == 'https' and r[1].scheme == 'http' and r[0].netloc == r[1].netloc),
    ('https_http_r', lambda r: r[0].scheme == 'https' and r[1].scheme == 'http' and r[0].netloc != r[1].netloc),
    ('https_https_l', lambda r: r[0].scheme == 'https' and r[1].scheme == 'https' and r[0].netloc == r[1].netloc),
    ('https_https_r', lambda r: r[0].scheme == 'https' and r[1].scheme == 'https' and r[0].netloc != r[1].netloc),
]

select = sqlContext.sql("""
    SELECT 
        url as url,
        sri.target as sri
    FROM cc LATERAL VIEW explode(subresources) T AS sri
    WHERE sri.integrity IS NOT NULL
    """).rdd.map(lambda r: (urlparse(r.url), urlparse(urljoin(r.url, r.sri))))

with open("07_elements_per_protocol.csv", "w") as file:
    file.write("protocol,elements\n")
    for l in lambdas:
        result = select.filter(l[1]).count()
        file.write("{}, {}\n".format(l[0], result))

print(select.filter(lambda r: r[0].scheme == 'https' and r[1].scheme == 'http').map(lambda r : (r[0].netloc, r[1].netloc)).take(100))



# ---------------------------

# Q8: Top-k urls and domains among sri

csv("08_topk_sri_url.csv", """
SELECT 
    substr(sri.target, instr(sri.target, '//') + 2) AS library, 
    count(*) AS number
FROM cc LATERAL VIEW explode(subresources) T AS sri
WHERE sri.target IS NOT NULL 
  AND sri.target LIKE 'http%'
  AND sri.integrity IS NOT NULL
GROUP BY library
ORDER BY number DESC
""")

csv("08_topk_sri_domain.csv", """
SELECT 
    substring_index(substring_index(sri.target, '/', 3), '/', -1) AS domain, 
    count(*) AS number
FROM cc LATERAL VIEW explode(subresources) T AS sri
WHERE sri.target IS NOT NULL 
  AND sri.target LIKE 'http%'
  AND sri.integrity IS NOT NULL
GROUP BY domain
ORDER BY number DESC
""")

# ---------------------------

# Q9: What is the distribution of the values for the crossorigin attribute?

sqlContext.sql("""
SELECT
    sri.crossorigin,
    count(*)
FROM cc LATERAL VIEW explode(subresources) T AS sri
WHERE sri.crossorigin IS NOT NULL 
GROUP BY sri.crossorigin
""").show(20, False)

sqlContext.sql("""
SELECT
    cc.url,
    sri.target,
    sri.crossorigin
FROM cc LATERAL VIEW explode(subresources) T AS sri
WHERE sri.crossorigin = 'use-credentials'
  AND substring_index(substring_index(url, '/', 3), '/', -1) != substring_index(substring_index(sri.target, '/', 3), '/', -1)
""").show(200, False)

# ---------------------------

# The list of web pages having a csp policy
# See: https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP
sqlContext.sql("""
SELECT count(*)
FROM cc
WHERE csp LIKE '%require-sri-for%'
""").show(100, False)

# The list of web pages having a cors policy
sqlContext.sql("""
SELECT url, cors
FROM cc
WHERE cors IS NOT NULL
""").show(100, False)