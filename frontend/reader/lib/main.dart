import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:http/http.dart' as http;

void main() {
  runApp(const ReaderApp());
}

const String baseUrl = 'http://localhost:8000'; // TODO: point to your FastAPI host.

class ReaderApp extends StatelessWidget {
  const ReaderApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Reading Assistant',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF0F6CBD)),
        textTheme: GoogleFonts.merriweatherTextTheme(),
        useMaterial3: true,
      ),
      home: const HomePage(),
    );
  }
}

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  JobStatus? job;
  Timer? poller;
  bool uploading = false;
  String? uploadError;

  @override
  void dispose() {
    poller?.cancel();
    super.dispose();
  }

  Future<void> _pickAndUpload() async {
    setState(() {
      uploadError = null;
    });
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['pdf'],
      withData: true,
    );
    if (result == null || result.files.isEmpty) return;
    final file = result.files.first;
    final bytes = file.bytes;
    if (bytes == null) {
      setState(() => uploadError = 'Unable to read file bytes.');
      return;
    }
    final title = _deriveTitle(file.name);
    await _uploadFile(bytes, file.name, title);
  }

  Future<void> _uploadFile(Uint8List bytes, String filename, String title) async {
    setState(() {
      uploading = true;
      uploadError = null;
    });
    try {
      final uri = Uri.parse('$baseUrl/documents/upload');
      final request = http.MultipartRequest('POST', uri)
        ..fields['title'] = title
        ..fields['author'] = ''
        ..fields['language'] = 'en'
        ..fields['perform_ocr'] = 'false'
        ..files.add(http.MultipartFile.fromBytes('file', bytes, filename: filename, contentType: null));
      final streamed = await request.send();
      final body = await streamed.stream.bytesToString();
      if (streamed.statusCode != 200) {
        throw Exception('Upload failed (${streamed.statusCode}): $body');
      }
      final data = json.decode(body) as Map<String, dynamic>;
      final bookId = data['book_id'] as String? ?? '';
      final jobId = data['job_id'] as String? ?? '';
      if (bookId.isEmpty || jobId.isEmpty) {
        throw Exception('Upload response missing book_id/job_id');
      }
      setState(() {
        job = JobStatus(jobId: jobId, bookId: bookId, state: 'queued');
      });
      _startPolling(jobId);
    } catch (e) {
      setState(() => uploadError = e.toString());
    } finally {
      setState(() {
        uploading = false;
      });
    }
  }

  void _startPolling(String jobId) {
    poller?.cancel();
    poller = Timer.periodic(const Duration(seconds: 1), (_) => _refreshJob(jobId));
  }

  Future<void> _refreshJob(String jobId) async {
    try {
      final resp = await http.get(Uri.parse('$baseUrl/jobs/$jobId'));
      if (resp.statusCode != 200) {
        throw Exception('Status ${resp.statusCode}');
      }
      final data = json.decode(resp.body) as Map<String, dynamic>;
      final status = JobStatus.fromJson(data);
      setState(() {
        job = status;
      });
      if (status.isTerminal) {
        poller?.cancel();
      }
    } catch (e) {
      setState(() => uploadError = 'Failed to fetch job: $e');
      poller?.cancel();
    }
  }

  String _deriveTitle(String filename) {
    final idx = filename.lastIndexOf('.');
    return idx > 0 ? filename.substring(0, idx) : filename;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Reading Assistant'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _UploadCard(
              onPick: uploading ? null : _pickAndUpload,
              uploading: uploading,
              error: uploadError,
            ),
            const SizedBox(height: 16),
            if (job != null) _JobStatusCard(job: job!),
            if (job != null && job!.state == 'completed')
              Align(
                alignment: Alignment.centerLeft,
                child: ElevatedButton.icon(
                  icon: const Icon(Icons.chrome_reader_mode),
                  label: const Text('Read book'),
                  onPressed: () {
                    Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => ReaderPage(docId: job!.bookId, pageNumber: 1),
                      ),
                    );
                  },
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _UploadCard extends StatelessWidget {
  const _UploadCard({required this.onPick, required this.uploading, this.error});

  final VoidCallback? onPick;
  final bool uploading;
  final String? error;

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Upload a book (PDF)', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Text(
              'Drag or click to select a PDF. Parsing starts automatically.',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 12),
            ElevatedButton.icon(
              icon: const Icon(Icons.upload_file),
              label: Text(uploading ? 'Uploading...' : 'Choose PDF'),
              onPressed: onPick,
            ),
            if (error != null)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(error!, style: TextStyle(color: Colors.red.shade700)),
              ),
          ],
        ),
      ),
    );
  }
}

class _JobStatusCard extends StatelessWidget {
  const _JobStatusCard({required this.job});

  final JobStatus job;

  @override
  Widget build(BuildContext context) {
    final progressText = job.totalPages != null && job.totalPages! > 0
        ? '${job.currentPage}/${job.totalPages}'
        : job.currentPage > 0
            ? '${job.currentPage} pages'
            : 'Pending';
    return Card(
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Job ${job.jobId}', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 6),
            Text('State: ${job.state} · Phase: ${job.phase ?? '-'}'),
            Text('Progress: $progressText'),
            if (job.errorMessage != null)
              Text('Error: ${job.errorMessage}', style: TextStyle(color: Colors.red.shade700)),
          ],
        ),
      ),
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
}

class ReaderPage extends StatefulWidget {
  const ReaderPage({super.key, required this.docId, required this.pageNumber});

  final String docId;
  final int pageNumber;

  @override
  State<ReaderPage> createState() => _ReaderPageState();
}

class _ReaderPageState extends State<ReaderPage> {
  late Future<PageData> parsedFuture;

  @override
  void initState() {
    super.initState();
    parsedFuture = _fetchParsedPage(widget.docId, widget.pageNumber);
  }

  @override
  Widget build(BuildContext context) {
    final isWide = MediaQuery.of(context).size.width >= 900;
    if (isWide) {
      return Scaffold(
        appBar: AppBar(
          title: Text('Doc ${widget.docId} · Page ${widget.pageNumber}'),
        ),
        body: Row(
          children: [
            Expanded(
              flex: 5,
              child: _OriginalPane(
                imageUrl: _pageImageUrl(widget.docId, widget.pageNumber),
              ),
            ),
            const VerticalDivider(width: 1),
            Expanded(
              flex: 5,
              child: _ParsedPane(parsedFuture: parsedFuture),
            ),
          ],
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Text('Doc ${widget.docId} · Page ${widget.pageNumber}'),
      ),
      body: PageView(
        children: [
          _OriginalPane(
            imageUrl: _pageImageUrl(widget.docId, widget.pageNumber),
          ),
          _ParsedPane(parsedFuture: parsedFuture),
        ],
      ),
    );
  }

  String _pageImageUrl(String docId, int page) =>
      '$baseUrl/documents/$docId/pages/$page/image';

  Future<PageData> _fetchParsedPage(String docId, int page) async {
    final url = Uri.parse('$baseUrl/documents/$docId/pages/$page/parsed');
    final resp = await http.get(url);
    if (resp.statusCode != 200) {
      throw Exception('Failed to load parsed page: ${resp.statusCode}');
    }
    final data = json.decode(resp.body) as Map<String, dynamic>;
    return PageData.fromJson(data);
  }
}

class _OriginalPane extends StatelessWidget {
  const _OriginalPane({required this.imageUrl});

  final String imageUrl;

  @override
  Widget build(BuildContext context) {
    return Container(
      color: Colors.grey.shade100,
      child: InteractiveViewer(
        minScale: 0.5,
        maxScale: 4,
        child: Center(
          child: Image.network(
            imageUrl,
            fit: BoxFit.contain,
            loadingBuilder: (context, child, progress) {
              if (progress == null) return child;
              return const Padding(
                padding: EdgeInsets.all(16),
                child: CircularProgressIndicator(),
              );
            },
            errorBuilder: (context, error, stack) {
              return Padding(
                padding: const EdgeInsets.all(16),
                child: Text('Failed to load page image\n$error'),
              );
            },
          ),
        ),
      ),
    );
  }
}

class _ParsedPane extends StatelessWidget {
  const _ParsedPane({required this.parsedFuture});

  final Future<PageData> parsedFuture;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<PageData>(
      future: parsedFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return Center(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Text('Error loading parsed text:\n${snapshot.error}'),
            ),
          );
        }
        final page = snapshot.data!;
        return Container(
          color: Colors.white,
          child: ListView.separated(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 24),
            itemCount: page.blocks.length,
            separatorBuilder: (_, __) => const SizedBox(height: 12),
            itemBuilder: (context, index) {
              final block = page.blocks[index];
              return _BlockCard(block: block);
            },
          ),
        );
      },
    );
  }
}

class _BlockCard extends StatelessWidget {
  const _BlockCard({required this.block});

  final BlockData block;

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 1,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              block.type.toUpperCase(),
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: Colors.grey.shade600,
                    letterSpacing: 1.1,
                  ),
            ),
            const SizedBox(height: 6),
            Text(
              block.text,
              style: Theme.of(context).textTheme.bodyLarge,
            ),
          ],
        ),
      ),
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
