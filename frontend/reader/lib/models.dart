class BookMeta {
  BookMeta({
    required this.id,
    required this.title,
    this.author,
    this.pageCount,
    this.status,
  });

  final String id;
  final String title;
  final String? author;
  final int? pageCount;
  final String? status;

  factory BookMeta.fromJson(Map<String, dynamic> json) {
    return BookMeta(
      id: json['id'] as String? ?? '',
      title: json['title'] as String? ?? '',
      author: json['author'] as String?,
      pageCount: (json['page_count'] as num?)?.toInt(),
      status: json['status'] as String?,
    );
  }
}

class JobStatus {
  JobStatus({
    required this.jobId,
    required this.bookId,
    required this.state,
    this.phase,
    this.currentPage = 0,
    this.totalPages,
    this.errorMessage,
  });

  final String jobId;
  final String bookId;
  final String state;
  final String? phase;
  final int currentPage;
  final int? totalPages;
  final String? errorMessage;

  bool get isTerminal => state == 'completed' || state == 'failed' || state == 'paused';

  factory JobStatus.fromJson(Map<String, dynamic> json) {
    return JobStatus(
      jobId: json['id'] as String? ?? '',
      bookId: json['book_id'] as String? ?? '',
      state: json['state'] as String? ?? 'unknown',
      phase: json['phase'] as String?,
      currentPage: (json['current_page'] as num? ?? 0).toInt(),
      totalPages: (json['total_pages'] as num?)?.toInt(),
      errorMessage: json['error_message'] as String?,
    );
  }

  JobStatus copyWith({
    String? state,
    String? phase,
    int? currentPage,
    int? totalPages,
    String? errorMessage,
  }) {
    return JobStatus(
      jobId: jobId,
      bookId: bookId,
      state: state ?? this.state,
      phase: phase ?? this.phase,
      currentPage: currentPage ?? this.currentPage,
      totalPages: totalPages ?? this.totalPages,
      errorMessage: errorMessage ?? this.errorMessage,
    );
  }
}

class SearchHit {
  SearchHit({
    required this.blockId,
    required this.pageNumber,
    required this.readingOrder,
    required this.text,
  });

  final String blockId;
  final int pageNumber;
  final int readingOrder;
  final String text;

  factory SearchHit.fromJson(Map<String, dynamic> json) {
    return SearchHit(
      blockId: json['block_id'] as String? ?? '',
      pageNumber: (json['page_number'] as num? ?? 0).toInt(),
      readingOrder: (json['reading_order'] as num? ?? 0).toInt(),
      text: json['text'] as String? ?? '',
    );
  }
}

class PageData {
  PageData({required this.blocks});

  final List<BlockData> blocks;

  factory PageData.fromJson(Map<String, dynamic> json) {
    final blocksJson = json['blocks'] as List<dynamic>? ?? [];
    final blocks = blocksJson
        .map((b) => BlockData.fromJson(b as Map<String, dynamic>))
        .toList()
      ..sort((a, b) => a.readingOrder.compareTo(b.readingOrder));
    return PageData(blocks: blocks);
  }
}

class BlockData {
  BlockData({
    required this.id,
    required this.text,
    required this.type,
    required this.readingOrder,
  });

  final String id;
  final String text;
  final String type;
  final int readingOrder;

  factory BlockData.fromJson(Map<String, dynamic> json) {
    if (!json.containsKey('text') || json['text'] == null) {
      throw const FormatException('Block text missing');
    }
    return BlockData(
      id: json['id'] as String? ?? '',
      text: json['text'] as String,
      type: json['block_type'] as String? ?? 'paragraph',
      readingOrder: (json['reading_order'] as num? ?? 0).toInt(),
    );
  }
}
