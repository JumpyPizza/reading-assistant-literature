import 'package:flutter/material.dart';

import '../models.dart';

class ParsedPane extends StatelessWidget {
  const ParsedPane({super.key, required this.parsedFuture, this.highlightQuery});

  final Future<PageData> parsedFuture;
  final String? highlightQuery;

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
              return _BlockCard(block: block, highlightQuery: highlightQuery);
            },
          ),
        );
      },
    );
  }
}

class _BlockCard extends StatelessWidget {
  const _BlockCard({required this.block, this.highlightQuery});

  final BlockData block;
  final String? highlightQuery;

  @override
  Widget build(BuildContext context) {
    final spans = [TextSpan(text: block.text)];
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
            RichText(
              text: TextSpan(
                style: Theme.of(context).textTheme.bodyLarge,
                children: spans,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
