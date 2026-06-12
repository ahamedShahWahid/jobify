import 'package:flutter/material.dart';

import 'package:jobify_app/presentation/theme/jobify_spacing.dart';

class JobifyLoadingView extends StatelessWidget {
  const JobifyLoadingView({super.key, this.message});

  final String? message;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const CircularProgressIndicator.adaptive(),
          if (message != null) ...[
            const SizedBox(height: JobifySpacing.lg),
            Text(message!, style: Theme.of(context).textTheme.bodyMedium),
          ],
        ],
      ),
    );
  }
}
