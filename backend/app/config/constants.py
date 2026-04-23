# Chat modes
CHAT_VECTOR_MODE = "vector"
CHAT_FULLTEXT_MODE = "fulltext"
CHAT_VECTOR_GRAPH_MODE = "graph_vector"
CHAT_VECTOR_GRAPH_FULLTEXT_MODE = "graph_vector_fulltext"
CHAT_DEFAULT_MODE = "graph_vector_fulltext"

# Search parameters
VECTOR_SEARCH_TOP_K = 5
CHAT_SEARCH_KWARG_SCORE_THRESHOLD = 0.5
VECTOR_GRAPH_SEARCH_ENTITY_LIMIT = 40
VECTOR_GRAPH_SEARCH_EMBEDDING_MIN_MATCH = 0.3
VECTOR_GRAPH_SEARCH_EMBEDDING_MAX_MATCH = 0.9
VECTOR_GRAPH_SEARCH_ENTITY_LIMIT_MINMAX = 20
VECTOR_GRAPH_SEARCH_ENTITY_LIMIT_MAX = 40

# Neo4j index names
VECTOR_INDEX_NAME = "vector"
FULLTEXT_INDEX_NAME = "keyword"
ENTITY_INDEX_NAME = "entity_vector"

# Retrieval queries
VECTOR_SEARCH_QUERY = """
WITH node AS chunk, score
MATCH (chunk)-[:PART_OF]->(d:Document)
WITH d,
     collect(distinct {chunk: chunk, score: score}) AS chunks,
     avg(score) AS avg_score
WITH d, avg_score,
     [c IN chunks | c.chunk.text] AS texts,
     [c IN chunks | {id: c.chunk.id, score: c.score}] AS chunkdetails
WITH d, avg_score, chunkdetails,
     apoc.text.join(texts, "\\n----\\n") AS text
RETURN text,
       avg_score AS score,
       {source: COALESCE(d.fileName, d.url),
        chunkdetails: chunkdetails} AS metadata
"""

VECTOR_GRAPH_SEARCH_QUERY = """
WITH node as chunk, score
MATCH (chunk)-[:PART_OF]->(d:Document)
WITH d, collect(DISTINCT {chunk: chunk, score: score}) AS chunks, avg(score) as avg_score
CALL { WITH chunks
UNWIND chunks as chunkScore
WITH chunkScore.chunk as chunk
    OPTIONAL MATCH (chunk)-[:HAS_ENTITY]->(e)
    WITH e, count(*) AS numChunks
    ORDER BY numChunks DESC
    LIMIT 40
    WITH
    CASE
        WHEN e.embedding IS NULL OR (0.3 <= vector.similarity.cosine($query_vector, e.embedding) AND vector.similarity.cosine($query_vector, e.embedding) <= 0.9) THEN
            collect {
                OPTIONAL MATCH path=(e)(()-[rels:!HAS_ENTITY&!PART_OF]-()){0,1}(:!Chunk&!Document&!__Community__)
                RETURN path LIMIT 20
            }
        WHEN e.embedding IS NOT NULL AND vector.similarity.cosine($query_vector, e.embedding) > 0.9 THEN
            collect {
                OPTIONAL MATCH path=(e)(()-[rels:!HAS_ENTITY&!PART_OF]-()){0,2}(:!Chunk&!Document&!__Community__)
                RETURN path LIMIT 40
            }
        ELSE
            collect {
                MATCH path=(e)
                RETURN path
            }
    END AS paths, e
   WITH apoc.coll.toSet(apoc.coll.flatten(collect(DISTINCT paths))) AS paths,
        collect(DISTINCT e) AS entities
   RETURN
       collect {
           UNWIND paths AS p
           UNWIND relationships(p) AS r
           RETURN DISTINCT r
       } AS rels,
       collect {
           UNWIND paths AS p
           UNWIND nodes(p) AS n
           RETURN DISTINCT n
       } AS nodes,
       entities
}
WITH d, avg_score,
    [c IN chunks | c.chunk.text] AS texts,
    [c IN chunks | {id: c.chunk.id, score: c.score}] AS chunkdetails,
    [n IN nodes | elementId(n)] AS entityIds,
    [r IN rels | elementId(r)] AS relIds,
    apoc.coll.sort([
        n IN nodes |
        coalesce(apoc.coll.removeAll(labels(n), ['__Entity__'])[0], "") + ":" +
        coalesce(n.id, "") +
        (CASE WHEN n.description IS NOT NULL THEN " (" + n.description + ")" ELSE "" END)
    ]) AS nodeTexts,
    apoc.coll.sort([
        r IN rels |
        coalesce(apoc.coll.removeAll(labels(startNode(r)), ['__Entity__'])[0], "") + ":" +
        coalesce(startNode(r).id, "") + " " + type(r) + " " +
        coalesce(apoc.coll.removeAll(labels(endNode(r)), ['__Entity__'])[0], "") + ":" +
        coalesce(endNode(r).id, "")
    ]) AS relTexts,
    entities
WITH d, avg_score, chunkdetails, entityIds, relIds,
    "Text Content:\\n" + apoc.text.join(texts, "\\n----\\n") +
    "\\n\\nEntities:\\n" + apoc.text.join(nodeTexts, "\\n") +
    "\\n\\nRelationships:\\n" + apoc.text.join(relTexts, "\\n") AS text,
    entities
RETURN
   text,
   avg_score AS score,
   {
       length: size(text),
       source: COALESCE(d.fileName, d.url),
       chunkdetails: chunkdetails,
       entities: {
           entityids: entityIds,
           relationshipids: relIds
       }
   } AS metadata
"""

# Chat mode config map
CHAT_MODE_CONFIG_MAP = {
    CHAT_VECTOR_MODE: {
        "retrieval_query": VECTOR_SEARCH_QUERY,
        "top_k": VECTOR_SEARCH_TOP_K,
        "index_name": VECTOR_INDEX_NAME,
        "keyword_index": None,
    },
    CHAT_FULLTEXT_MODE: {
        "retrieval_query": VECTOR_SEARCH_QUERY,
        "top_k": VECTOR_SEARCH_TOP_K,
        "index_name": VECTOR_INDEX_NAME,
        "keyword_index": FULLTEXT_INDEX_NAME,
    },
    CHAT_VECTOR_GRAPH_MODE: {
        "retrieval_query": VECTOR_GRAPH_SEARCH_QUERY,
        "top_k": VECTOR_SEARCH_TOP_K,
        "index_name": VECTOR_INDEX_NAME,
        "keyword_index": None,
    },
    CHAT_VECTOR_GRAPH_FULLTEXT_MODE: {
        "retrieval_query": VECTOR_GRAPH_SEARCH_QUERY,
        "top_k": VECTOR_SEARCH_TOP_K,
        "index_name": VECTOR_INDEX_NAME,
        "keyword_index": FULLTEXT_INDEX_NAME,
    },
}

# LLM System prompt
CHAT_SYSTEM_TEMPLATE = """
Bạn là trợ lý AI của Đài Phát thanh và Truyền hình Hải Phòng, hỗ trợ phòng Quảng cáo – Kinh doanh.

### Nguyên tắc trả lời:
1. Trả lời chính xác, ngắn gọn dựa trên ngữ cảnh được cung cấp.
2. Tận dụng lịch sử hội thoại để duy trì ngữ cảnh liên tục.
3. Nếu câu hỏi không liên quan đến quảng cáo/tài liệu, trả lời thân thiện và gợi ý quay lại chủ đề quảng cáo.
4. KHÔNG bịa đặt thông tin ngoài ngữ cảnh.
5. Nếu có ngữ cảnh, ghi rõ nguồn tài liệu. Nếu không có ngữ cảnh nhưng câu hỏi hợp lệ, trả lời dựa trên kiến thức về Đài PT-TH Hải Phòng.

### QUY TẮC FORMAT SỐ TIỀN (RẤT QUAN TRỌNG):
- Tất cả số tiền phải có dấu chấm phân cách hàng nghìn
- ĐÚNG: 5.000.000 đồng, 100.000.000 đồng
- SAI: 5000000 đồng, 100000000 đồng
- KHÔNG được viết số liền không có dấu chấm

**QUAN TRỌNG**: CHỈ trả lời dựa trên ngữ cảnh bên dưới, không dùng kiến thức bên ngoài.

### Ngữ cảnh:
<context>
{context}
</context>
"""

CALCULATE_WITH_TOOLS_PROMPT = """
Bạn là chuyên viên tính chi phí quảng cáo của Đài PT-TH Hải Phòng.
Bạn có các tools để tra giá và tính toán chính xác. Hãy dùng tools thay vì tự tính.
 
Quy tắc:
1. Luôn dùng tool để lấy đơn giá, KHÔNG tự nhớ hoặc đoán giá
2. Gọi tool theo thứ tự: lookup_price -> calculate_cost -> calculate_discount
3. Nếu là DNHP (khách Hải Phòng) và số lần phát nhiều -> gọi thêm check_package
4. Trình bày kết quả rõ ràng: đơn giá -> tổng -> chiết khấu -> thành tiền
5. Ghi rõ áp dụng bảng giá nào (QĐ 414 hay QĐ 415)
 
Lưu ý phân biệt bảng giá:
- Khách trên địa bàn Hải Phòng -> dùng "dnhp" (QĐ 415, giá thấp hơn)
- Khách ngoài Hải Phòng hoặc không rõ -> dùng "tong_hop" (QĐ 414)
- Phóng sự/phim tài liệu -> dùng tool_calculate_documentary_cost (QĐ 413)

QUY TẮC ĐỊNH DẠNG SỐ TIỀN TRONG LATEX:
- Dùng \\{,} thay cho dấu chấm phân cách hàng nghìn trong math block
- VÍ DỤ ĐÚNG: $19{,}000{,}000$ VND, $100{,}700{,}000$
- VÍ DỤ SAI: $19.000.000$ (dấu chấm bị KaTeX xử lý sai)
- Luôn đặt số tiền trong $...$ (inline) hoặc \\[...\\] (display)
- Trong table cell, dùng \\text{...} để wrap số: \\text{19{,}000{,}000} VND
- Khi cần khoảng trắng trong math, dùng \\, thay vì \\ (backslash-space)
  * ĐÚNG: \\text{Chiết khấu}=0\\,\\text{VND}
  * SAI: \\text{Chiết khấu}=0\\ \\text{VND} (sẽ bị lỗi)
"""

QUESTION_TRANSFORM_TEMPLATE = "Dựa trên cuộc hội thoại bên dưới, hãy tạo một câu truy vấn tìm kiếm để lấy thông tin liên quan. Chỉ trả về câu truy vấn, không thêm gì khác."

INTENT_CLASSIFICATION_TEMPLATE = """
Phân loại câu hỏi vào 1 trong 2 nhóm:
- qa        : hỏi giá, tra cứu bảng giá, đơn giá dịch vụ quảng cáo truyền hình, phát thanh, báo
- calculate : tính toán chi phí, tính tổng tiền, yêu cầu báo giá cụ thể với số lượng

Ví dụ:
Câu hỏi: "Đơn giá quảng cáo khung giờ HP8 trên kênh THP là bao nhiêu?"
Intent: qa

Câu hỏi: "Giá banner 300x250 pixel trang chủ báo điện tử đăng 1 tháng là bao nhiêu?"
Intent: qa

Câu hỏi: "Phụ cấp lưu trú khi đi công tác tại Hà Nội theo Quy chế chi tiêu nội bộ BPTTH là bao nhiêu?"
Intent: qa

Câu hỏi: "Tính tổng tiền cho 3 spot 30 giây khung giờ T1 trên kênh THP?"
Intent: calculate

Câu hỏi: "Chạy 5 spot 45 giây khung giờ S3 trên kênh THP hết bao nhiêu?"
Intent: calculate

Câu hỏi: "Đặt spot T3 vị trí ưu tiên số 1 (30 giây) tốn thêm bao nhiêu so với giá thường?"
Intent: calculate

Câu hỏi: "Hợp đồng 135 lần quảng cáo khung giờ HP11, doanh số bao nhiêu và được chiết khấu mấy phần trăm?"
Intent: calculate

Chỉ trả về đúng 1 từ: qa hoặc calculate
"""

SUGGESTIONS_TEMPLATE = """Dựa trên câu hỏi và câu trả lời bên dưới, hãy gợi ý 2-3 câu hỏi tiếp theo mà khách hàng thường quan tâm.

Trả lời theo format: câu hỏi 1 | câu hỏi 2 | câu hỏi 3
Mỗi câu hỏi phải ngắn gọn (dưới 30 từ).
Không thêm giải thích gì khác."""
