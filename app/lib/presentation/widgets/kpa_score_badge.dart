import 'package:flutter/material.dart';

import 'package:kpa_app/presentation/theme/kpa_colors.dart';
import 'package:kpa_app/presentation/theme/kpa_radii.dart';
import 'package:kpa_app/presentation/theme/kpa_spacing.dart';

class KpaScoreBadge extends StatelessWidget {
  const KpaScoreBadge({required this.score, super.key});

  final double score;

  Color get _bandColor {
    if (score >= 0.80) return KpaColors.scoreHigh;
    if (score >= 0.65) return KpaColors.scoreMid;
    return KpaColors.scoreLow;
  }

  @override
  Widget build(BuildContext context) {
    final percent = (score * 100).round().clamp(0, 100);
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: KpaSpacing.sm,
        vertical: KpaSpacing.xs,
      ),
      decoration: BoxDecoration(
        color: _bandColor,
        borderRadius: KpaRadii.borderRadiusPill,
      ),
      child: Text(
        '$percent%',
        style: Theme.of(context).textTheme.labelMedium?.copyWith(
              color: KpaColors.neutral0,
            ),
      ),
    );
  }
}
