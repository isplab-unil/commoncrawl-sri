from pyspark.shell import sqlContext

sqlContext.read.parquet("output/*.parquet").registerTempTable("cc")

# ---------------------------
# -------- GENERAL ----------
# ---------------------------

# What is the number of pages that have been processed?
sqlContext.sql("""
SELECT count(*) AS number FROM cc
""").show()

# What is the number of warc files that have been processed?
sqlContext.sql("""
SELECT count(DISTINCT warc) AS number FROM cc
""").show()

# What is the number of pages by protocol?
sqlContext.sql("""
SELECT 
    if(uri LIKE 'https%', 'https', if(uri LIKE 'http%', 'http', 'other')) AS protocol, 
    round(100 * count(*) / (SELECT count(*) FROM cc), 2) AS percentage 
FROM cc 
GROUP BY protocol
""").show()

# ---------------------------
# ---------- SRI ------------
# ---------------------------

# What is the percentage of pages that includes at least one tag with the integrity attribute?
sqlContext.sql("""
SELECT 
    round(100 * count(*) / (SELECT count(*) AS uris FROM cc), 2) AS percentage 
FROM cc 
WHERE has_subresource = true 
  AND size(filter(subresources, s -> s.integrity IS NOT NULL)) > 0
""").show()

# What is the percentage of pages that includes at least one script with the integrity attribute?
sqlContext.sql("""
SELECT 
    round(100 * count(*) / (SELECT count(*) AS uris FROM cc), 2) AS percentage 
FROM cc 
WHERE has_subresource = true 
  AND size(filter(subresources, s -> s.name == 'script' AND s.integrity IS NOT NULL)) > 0
""").show()

# What is the percentage of pages that includes at least one link with the integrity attribute?
sqlContext.sql("""
SELECT 
    round(100 * count(*) / (SELECT count(*) AS uris FROM cc), 2) AS percentage 
FROM cc 
WHERE has_subresource = true 
  AND size(filter(subresources, s -> s.name == 'link' AND s.integrity IS NOT NULL)) > 0
""").show()

# ---------------------------

# What is the distribution of pages by number of SRI tags?
sqlContext.sql("""
SELECT 
    size(filter(subresources, s -> s.integrity IS NOT NULL)) AS tags, 
    count(*) AS number 
FROM cc 
WHERE has_subresource = true 
  AND size(filter(subresources, s -> s.integrity IS NOT NULL)) > 0 
GROUP BY tags 
ORDER BY tags ASC
""").show()

# What is the distribution of pages by scripts?
sqlContext.sql("""
SELECT 
    sri.target AS script, 
    count(*) AS number 
FROM (
    SELECT filter(subresources, s -> s.name == 'script' AND s.target IS NOT NULL AND s.integrity IS NOT NULL) AS subresources 
    FROM cc 
    WHERE has_subresource = true 
      AND size(filter(subresources, s -> s.name == 'script' AND s.target IS NOT NULL AND s.integrity IS NOT NULL)) > 0
) LATERAL VIEW explode(subresources) T AS sri 
GROUP BY script 
ORDER BY number DESC
""").show()

# What is the distribution of pages by links?
sqlContext.sql("""
SELECT 
    sri.target AS link, 
    count(*) AS number 
FROM (
    SELECT filter(subresources, s -> s.name == 'link' AND s.target IS NOT NULL AND s.integrity IS NOT NULL) AS subresources 
    FROM cc 
    WHERE has_subresource = true 
      AND size(filter(subresources, s -> s.name == 'link' AND s.target IS NOT NULL AND s.integrity IS NOT NULL)) > 0
) LATERAL VIEW explode(subresources) T AS sri 
GROUP BY link 
ORDER BY number DESC
""").show()

# ---------------------------

# What is the distribution of tags with integrity attribute per protocol?
sqlContext.sql("""
SELECT if(sri.target LIKE 'https%', 'https', if(sri.target LIKE 'http%', 'http', if(uri LIKE 'https%', 'https', 'http'))) AS protocol, count(*) as tag_targets FROM (
    SELECT uri, filter(subresources, s -> s.integrity IS NOT NULL) AS subresources 
    FROM cc 
    WHERE has_subresource = true 
      AND size(filter(subresources, s -> s.integrity IS NOT NULL)) > 0
) LATERAL VIEW explode(subresources) T AS sri
GROUP BY protocol
ORDER BY tag_targets DESC
""").show()

# What is the distribution of scripts with integrity attribute per protocol?
sqlContext.sql("""
SELECT if(sri.target LIKE 'https%', 'https', if(sri.target LIKE 'http%', 'http', if(uri LIKE 'https%', 'https', 'http'))) AS protocol, count(*) as script_targets FROM (
    SELECT uri, filter(subresources, s -> s.name == 'script' AND s.integrity IS NOT NULL) AS subresources 
    FROM cc 
    WHERE has_subresource = true 
      AND size(filter(subresources, s -> s.name == 'script' AND s.integrity IS NOT NULL)) > 0
) LATERAL VIEW explode(subresources) T AS sri
GROUP BY protocol
ORDER BY script_targets DESC
""").show()

# What is the distribution of links with integrity attribute per protocol?
sqlContext.sql("""
SELECT if(sri.target LIKE 'https%', 'https', if(sri.target LIKE 'http%', 'http', if(uri LIKE 'https%', 'https', 'http'))) AS protocol, count(*) as link_targets FROM (
    SELECT uri, filter(subresources, s -> s.name == 'link' AND s.integrity IS NOT NULL) AS subresources 
    FROM cc 
    WHERE has_subresource = true 
      AND size(filter(subresources, s -> s.name == 'link' AND s.integrity IS NOT NULL)) > 0
) LATERAL VIEW explode(subresources) T AS sri
GROUP BY protocol
ORDER BY link_targets DESC
""").show()

# ---------------------------

# What is the percentage of tags that specifies the integrity attribute on a page that includes at least one tag with the integrity attribute?
sqlContext.sql("""
SELECT 
    round(100 * sum(size(filter(subresources, s -> s.integrity IS NOT NULL))) / sum(size(subresources)), 2) AS percentage
FROM cc 
WHERE has_subresource = true 
  AND size(filter(subresources, s -> s.integrity IS NOT NULL)) > 0
""").show()

# What is the percentage of scripts that specifies the integrity attribute on a page that includes at least one script with the integrity attribute?
sqlContext.sql("""
SELECT 
    round(100 * sum(size(filter(subresources, s -> s.name == 'script' AND s.integrity IS NOT NULL))) / sum(size(filter(subresources, s -> s.name == 'script'))), 2) AS percentage
FROM cc 
WHERE has_subresource = true 
  AND size(filter(subresources, s -> s.name == 'script' AND s.integrity IS NOT NULL)) > 0
""").show()

# What is the percentage of links that specifies the integrity attribute on a page that includes at least one link with the integrity attribute?
sqlContext.sql("""
SELECT 
    round(100 * sum(size(filter(subresources, s -> s.name == 'link' AND s.integrity IS NOT NULL))) / sum(size(filter(subresources, s -> s.name == 'link'))), 2) AS percentage
FROM cc 
WHERE has_subresource = true 
  AND size(filter(subresources, s -> s.name == 'link' AND s.integrity IS NOT NULL)) > 0
""").show()

# ---------------------------

# What is the number of pages by hashing algorithms?
sqlContext.sql("""
SELECT 
    substr(sri.integrity, 0, 6) as hash, 
    count(*)
FROM cc LATERAL VIEW explode(subresources) T AS sri
WHERE has_subresource = true 
  AND sri.integrity IS NOT NULL
GROUP BY hash
""").show()

# ---------------------------

# What are the most popular subresources included in pages
sqlContext.sql("""
SELECT 
    substr(sri.target, instr(sri.target, '//') + 2) AS library, 
    count(*) AS number
FROM cc LATERAL VIEW explode(subresources) T AS sri
WHERE sri.target IS NOT NULL AND sri.integrity IS NOT NULL
GROUP BY library
ORDER BY number DESC
""").show()

# ---------------------------
# ------- CHECKSUMS ---------
# ---------------------------

# How many pages contain at least one checksum
sqlContext.sql("""
SELECT 
    round(100 * count(*) / (SELECT count(*) FROM cc), 2) AS percentage 
FROM cc 
WHERE has_checksum = true AND size(checksums) > 0
""").show()

# ---------------------------
# -------- HEADERS ----------
# ---------------------------

sqlContext.sql("""
SELECT csp, count(*) as number
FROM cc
GROUP BY csp
ORDER BY number DESC
""").show()

sqlContext.sql("""
SELECT cors, count(*) as number
FROM cc
GROUP BY cors
ORDER BY number DESC
""").show()