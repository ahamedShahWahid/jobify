import 'package:flutter/material.dart';

import 'package:jobify_app/presentation/theme/jobify_colors.dart';
import 'package:jobify_app/presentation/theme/jobify_radii.dart';
import 'package:jobify_app/presentation/theme/jobify_spacing.dart';

class JobifyScoreBadge extends StatelessWidget {
  const JobifyScoreBadge({required this.score, super.key});

  final double score;

  Color get _bandColor {
    if (score >= 0.80) return JobifyColors.scoreHigh;
    if (score >= 0.65) return JobifyColors.scoreMid;
    return JobifyColors.scoreLow;
  }

  @override
  Widget build(BuildContext context) {
    final percent = (score * 100).round().clamp(0, 100);
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: JobifySpacing.sm,
        vertical: JobifySpacing.xs,
      ),
      decoration: BoxDecoration(
        color: _bandColor,
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
