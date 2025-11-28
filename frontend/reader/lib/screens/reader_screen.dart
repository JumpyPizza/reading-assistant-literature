import 'dart:async';

import 'package:flutter/material.dart';

import '../models.dart';
import '../services/api_client.dart';
import '../widgets/parsed_pane.dart';
import '../widgets/reader_controls.dart';

class ReaderScreen extends StatefulWidget {
  const ReaderScreen({super.key, required this.docId, required this.pageNumber});

  final String docId;
  final int pageNumber;

  @override
  State<ReaderScreen> createState() => _ReaderScreenState();
}

class _ReaderScreenState extends State<ReaderScreen> {
  final ApiClient api = const ApiClient();
  late Future<PageData> parsedFuture;
  int currentPage = 1;
  int? totalPages;
  String? readerError;
  bool loadingPage = false;

  final TextEditingController pageController = TextEditingController();

  @override
  void initState() {
    super.initState();
    currentPage = widget.pageNumber;
    pageController.text = currentPage.toString();
    _loadBookMeta();
    _loadPage();
  }

  @override
  void dispose() {
    pageController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isWide = MediaQuery.of(context).size.width >= 900;
    final bodyContent = isWide
        ? Row(
            children: [
              Expanded(
                flex: 5,
                child: _OriginalPane(
                  imageUrl: api.pageImageUrl(widget.docId, currentPage),
                ),
              ),
              const VerticalDivider(width: 1),
              Expanded(
                flex: 5,
                child: ParsedPane(
                  parsedFuture: parsedFuture,
                  highlightQuery: null,
                ),
              ),
            ],
          )
        : PageView(
            children: [
              _OriginalPane(
                imageUrl: api.pageImageUrl(widget.docId, currentPage),
              ),
              ParsedPane(
                parsedFuture: parsedFuture,
                highlightQuery: null,
              ),
            ],
          );

    return Scaffold(
      appBar: AppBar(
        title: Text('Doc ${widget.docId}'),
      ),
      body: Column(
        children: [
          ReaderControls(
            pageController: pageController,
            totalPages: totalPages,
            onPrev: _prevPage,
            onNext: _nextPage,
            onGo: _goToInputPage,
          ),
          if (readerError != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
              child: Text(
                readerError!,
                style: TextStyle(color: Colors.red.shade700),
              ),
            ),
          Expanded(child: bodyContent),
        ],
      ),
    );
  }

  Future<void> _loadBookMeta() async {
    try {
      final meta = await api.getBook(widget.docId);
      setState(() {
        totalPages = meta.pageCount;
      });
    } catch (_) {
      // ignore meta errors
    }
  }

  void _loadPage() {
    setState(() {
      loadingPage = true;
      parsedFuture = api.fetchParsedPage(widget.docId, currentPage);
    });
    parsedFuture.whenComplete(() {
      if (mounted) {
        setState(() {
          loadingPage = false;
        });
      }
    });
  }

  void _prevPage() {
    if (currentPage <= 1) return;
    setState(() {
      currentPage -= 1;
      pageController.text = currentPage.toString();
    });
    _loadPage();
  }

  void _nextPage() {
    if (totalPages != null && currentPage >= totalPages!) return;
    setState(() {
      currentPage += 1;
      pageController.text = currentPage.toString();
    });
    _loadPage();
  }

  void _goToInputPage() {
    final input = int.tryParse(pageController.text.trim());
    if (input == null || input <= 0) return;
    if (totalPages != null && input > totalPages!) return;
    setState(() {
      currentPage = input;
    });
    _loadPage();
  }

  Future<void> _performSearch() async {
    // Search removed for now.
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
