import 'package:flutter/material.dart';

class ReaderControls extends StatelessWidget {
  const ReaderControls({
    super.key,
    required this.pageController,
    required this.totalPages,
    required this.onPrev,
    required this.onNext,
    required this.onGo,
  });

  final TextEditingController pageController;
  final int? totalPages;
  final VoidCallback onPrev;
  final VoidCallback onNext;
  final VoidCallback onGo;

  @override
  Widget build(BuildContext context) {
    final totalText = totalPages != null ? '/$totalPages' : '';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      color: Colors.grey.shade100,
      child: Column(
        children: [
          Row(
            children: [
              IconButton(onPressed: onPrev, icon: const Icon(Icons.chevron_left)),
              SizedBox(
                width: 80,
                child: TextField(
                  controller: pageController,
                  keyboardType: TextInputType.number,
                  decoration: InputDecoration(
                    isDense: true,
                    labelText: 'Page',
                    suffixText: totalText,
                  ),
                  onSubmitted: (_) => onGo(),
                ),
              ),
              const SizedBox(width: 8),
              ElevatedButton(onPressed: onGo, child: const Text('Go')),
              IconButton(onPressed: onNext, icon: const Icon(Icons.chevron_right)),
            ],
          ),
        ],
      ),
    );
  }
}
