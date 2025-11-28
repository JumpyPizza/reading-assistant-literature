import 'package:flutter/material.dart';

import '../models.dart';

class AvailableBooks extends StatelessWidget {
  const AvailableBooks({super.key, required this.books, required this.onOpen});

  final List<BookMeta> books;
  final ValueChanged<String> onOpen;

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 1,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Available books', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: books
                  .map(
                    (b) => ActionChip(
                      label: Text(b.title.isNotEmpty ? b.title : b.id),
                      onPressed: () => onOpen(b.id),
                    ),
                  )
                  .toList(),
            ),
          ],
        ),
      ),
    );
  }
}
