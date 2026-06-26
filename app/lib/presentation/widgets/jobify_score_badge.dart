import 'package:flutter/material.dart';

import 'package:jobify_app/presentation/theme/jobify_colors.dart';
import 'package:jobify_app/presentation/theme/jobify_radii.dart';
import 'package:jobify_app/presentation/theme/jobify_spacing.dart';

class JobifyScoreBadge extends StatelessWidget {
  const JobifyScoreBadge({required this.score, super.key});

  final double score;

  // TODO(task-3): replace with score-band colours from Clear Sky palette.
  Color _bandColor(bool isDark) =>
      isDark ? JobifyColors.brandBlueDark : JobifyColors.brandBlueLight;

  @override
  Widget build(BuildContext context) {
    final percent = (score * 100).round().clamp(0, 100);
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: JobifySpacing.sm,
        vertical: JobifySpacing.xs,
      ),
      decoration: BoxDecoration(
        color: _bandColor(Theme.of(context).brightness == Brightness.dark),
        borderRadius: JobifyRadii.borderRadiusPill,
      ),
      child: Text(
        '$percent%',
        style: Theme.of(context).textTheme.labelMedium?.copyWith(
              color: Colors.white,
            ),
      ),
    );
  }
}
