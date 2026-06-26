import 'package:flutter/material.dart';

import 'package:jobify_app/presentation/theme/jobify_colors.dart';
import 'package:jobify_app/presentation/theme/jobify_typography.dart';

/// The match score, demoted to a quiet monospace stamp.
///
/// Brand blue when the match is strong (>= 0.80) — "worth your attention" —
/// otherwise inkSoft. No filled pill: the *sentence* is the hero, not the
/// number.
class JobifyScoreBadge extends StatelessWidget {
  const JobifyScoreBadge({required this.score, super.key});

  final double score;

  static bool isStrong(double score) => score >= 0.80;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final percent = (score * 100).round().clamp(0, 100);
    final color = isStrong(score)
        ? (isDark ? JobifyColors.brandBlueDark : JobifyColors.brandBlueLight)
        : (isDark ? JobifyColors.inkSoftDark : JobifyColors.inkSoftLight);
    return Text(
      '$percent%',
      style: JobifyTypography.mono(
        fontSize: 13,
        fontWeight: FontWeight.w600,
        color: color,
        letterSpacing: -0.2,
      ),
    );
  }
}
