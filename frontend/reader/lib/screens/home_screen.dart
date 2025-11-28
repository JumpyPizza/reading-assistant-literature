import 'dart:async';
import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dropzone/flutter_dropzone.dart';
import 'package:flutter_dropzone_platform_interface/flutter_dropzone_platform_interface.dart';

import '../models.dart';
import '../services/api_client.dart';
import '../widgets/available_books.dart';
import '../widgets/upload_card.dart';
import 'reader_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final ApiClient api = const ApiClient();
  JobStatus? job;
  Timer? poller;
  bool uploading = false;
  String? uploadError;
  List<BookMeta> availableBooks = [];
  DropzoneViewController? dropzoneController;

  @override
  void initState() {
    super.initState();
    _loadBooks();
  }

  @override
  void dispose() {
    poller?.cancel();
    super.dispose();
  }

  Future<void> _loadBooks() async {
    try {
      final books = await api.listBooks();
      setState(() {
        availableBooks = books.where((b) => b.status == 'parsed').toList();
      });
    } catch (_) {
      // ignore for now
    }
  }

  Future<void> _pickAndUpload() async {
    setState(() {
      uploadError = null;
    });
    final title = await _promptTitle();
    if (title == null || title.isEmpty) return;

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
    await _uploadFile(bytes, file.name, title);
  }

  Future<String?> _promptTitle() async {
    final titleController = TextEditingController();
    final formResult = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Enter book title'),
        content: TextField(
          controller: titleController,
          decoration: const InputDecoration(labelText: 'Title'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, titleController.text.trim()),
            child: const Text('Continue'),
          ),
        ],
      ),
    );
    return formResult;
  }

  Future<void> _uploadFile(Uint8List bytes, String filename, String title) async {
    setState(() {
      uploading = true;
      uploadError = null;
    });
    try {
      final ids = await api.uploadDocument(bytes: bytes, filename: filename, title: title);
      setState(() {
        job = JobStatus(jobId: ids["job_id"]!, bookId: ids["book_id"]!, state: 'queued');
      });
      final proceed = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Start parsing?'),
          content: Text('Book "$title" uploaded. Start parsing now?'),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Back')),
            ElevatedButton(onPressed: () => Navigator.pop(context, true), child: const Text('Continue')),
          ],
        ),
      );
      if (proceed == true && job != null) {
        _startPolling(ids["job_id"]!);
      } else {
        // User chose not to start; clear job so UI stays on upload.
        setState(() {
          job = null;
        });
      }
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
    poller = Timer.periodic(const Duration(seconds: 5), (_) => _refreshJob(jobId));
  }

  Future<void> _refreshJob(String jobId) async {
    try {
      final status = await api.getJob(jobId);
      setState(() {
        job = status;
      });
      if (status.isTerminal) {
        poller?.cancel();
        _loadBooks();
      }
    } catch (e) {
      setState(() => uploadError = 'Failed to fetch job: $e');
      poller?.cancel();
    }
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
            UploadCard(
              onPick: uploading ? null : _pickAndUpload,
              uploading: uploading,
              error: uploadError,
              dropZone: _buildDropZone(),
            ),
            const SizedBox(height: 16),
            if (availableBooks.isNotEmpty)
              AvailableBooks(
                books: availableBooks.where((b) => b.status == 'parsed').toList(),
                onOpen: (bookId) {
                  Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => ReaderScreen(docId: bookId, pageNumber: 1),
                    ),
                  );
                },
              ),
            const SizedBox(height: 16),
            if (job != null)
              _JobStatusCard(
                job: job!,
                onCancel: () async {
                  try {
                    await api.cancelJob(job!.jobId);
                    setState(() {
                      job = job!.copyWith(state: 'paused', errorMessage: 'Cancelled by user');
                    });
                    poller?.cancel();
                  } catch (e) {
                    setState(() {
                      uploadError = 'Failed to cancel: $e';
                    });
                  }
                },
              ),
            if (job != null && job!.state == 'completed')
              Align(
                alignment: Alignment.centerLeft,
                child: ElevatedButton.icon(
                  icon: const Icon(Icons.chrome_reader_mode),
                  label: const Text('Read book'),
                  onPressed: () {
                    Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => ReaderScreen(docId: job!.bookId, pageNumber: 1),
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

  Widget _buildDropZone() {
    return Container(
      height: 120,
      decoration: BoxDecoration(
        border: Border.all(color: Colors.blueGrey.shade200, style: BorderStyle.solid),
        borderRadius: BorderRadius.circular(8),
        color: Colors.blueGrey.shade50,
      ),
      child: Stack(
        children: [
          DropzoneView(
            onCreated: (ctrl) => dropzoneController = ctrl,
            mime: const ['application/pdf'],
            onDropFile: (DropzoneFileInterface file) async {
              if (uploading) return;
              try {
                final bytes = await dropzoneController?.getFileData(file);
                if (bytes == null) return;
                final title = await _promptTitle();
                if (title == null || title.isEmpty) return;
                await _uploadFile(bytes, file.name ?? 'uploaded.pdf', title);
              } catch (e) {
                setState(() => uploadError = 'Drop failed: $e');
              }
            },
          ),
          Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: const [
                Icon(Icons.cloud_upload, size: 32, color: Colors.blueGrey),
                SizedBox(height: 8),
                Text('Drop PDF here'),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _JobStatusCard extends StatelessWidget {
  const _JobStatusCard({required this.job, required this.onCancel});

  final JobStatus job;
  final VoidCallback onCancel;

  @override
  Widget build(BuildContext context) {
    const progressText = 'Parsing...';
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
            const SizedBox(height: 8),
            if (!job.isTerminal)
              ElevatedButton.icon(
                onPressed: onCancel,
                icon: const Icon(Icons.stop),
                label: const Text('Cancel job'),
                style: ElevatedButton.styleFrom(backgroundColor: Colors.red.shade600, foregroundColor: Colors.white),
              ),
          ],
        ),
      ),
    );
  }
}
