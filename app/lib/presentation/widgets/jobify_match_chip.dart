import 'package:flutter/material.dart';

import 'package:jobify_app/presentation/theme/jobify_colors.dart';
import 'package:jobify_app/presentation/theme/jobify_radii.dart';

/// A value that feeds the match directly (a targeted location) — wears the
/// one meaning-carrying color, brand blue, rather than a neutral chip.
/// Shared between the preferences capture flow and Edit Profile so the same
/// value reads the same way wherever it's edited.
class JobifyMatchChip extends StatelessWidget {
  const JobifyMatchChip({
    required this.label,
    required this.onDeleted,
    super.key,
  });

  final String label;
  final VoidCallback onDeleted;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final tint = isDark
        ? JobifyColors.brandBlueTintDark
        : JobifyColors.brandBlueTintLight;
    final ink =
        isDark ? JobifyColors.brandBlueDark : JobifyColors.brandBlueLight;
    return Chip(
      label: Text(label),
      labelStyle: TextStyle(color: ink, fontWeight: FontWeight.w600),
      backgroundColor: tint,
      side: BorderSide.none,
      shape: const RoundedRectangleBorder(
        borderRadius: JobifyRadii.borderRadiusPill,
      ),
      deleteIcon: Icon(Icons.close, size: 16, color: ink),
      onDeleted: onDeleted,
    );
  }
}
