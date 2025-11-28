import 'package:flutter/material.dart';

class UploadCard extends StatelessWidget {
  const UploadCard({
    super.key,
    required this.onPick,
    required this.uploading,
    this.error,
    this.dropZone,
  });

  final VoidCallback? onPick;
  final bool uploading;
  final String? error;
  final Widget? dropZone;

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
              'Drag a PDF here or click to select. Parsing starts after confirmation.',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 12),
            if (dropZone != null) dropZone!,
            const SizedBox(height: 8),
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
