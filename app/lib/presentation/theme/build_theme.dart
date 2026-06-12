import 'package:flutter/material.dart';

import 'package:jobify_app/presentation/theme/jobify_colors.dart';
import 'package:jobify_app/presentation/theme/jobify_radii.dart';
import 'package:jobify_app/presentation/theme/jobify_typography.dart';

/// Single ThemeData factory for both brightness modes. v0 only ever calls
/// this with [Brightness.light]; the dark branch is plumbed so flipping
/// `themeMode` later is a one-line change.
ThemeData buildTheme(Brightness brightness) {
  final isDark = brightness == Brightness.dark;
  final scheme = ColorScheme(
    brightness: brightness,
    primary: JobifyColors.indigo500,
    onPrimary: JobifyColors.neutral0,
    primaryContainer: isDark ? JobifyColors.indigo700 : JobifyColors.indigo100,
    onPrimaryContainer:
        isDark ? JobifyColors.indigo100 : JobifyColors.indigo900,
    secondary: JobifyColors.indigo400,
    onSecondary: JobifyColors.neutral0,
    secondaryContainer: isDark ? JobifyColors.indigo800 : JobifyColors.indigo50,
    onSecondaryContainer:
        isDark ? JobifyColors.indigo50 : JobifyColors.indigo800,
    error: JobifyColors.error,
    onError: JobifyColors.onError,
    surface: isDark ? JobifyColors.neutral900 : JobifyColors.neutral0,
    onSurface: isDark ? JobifyColors.neutral50 : JobifyColors.neutral900,
    surfaceContainerHighest:
        isDark ? JobifyColors.neutral800 : JobifyColors.neutral50,
    onSurfaceVariant:
        isDark ? JobifyColors.neutral300 : JobifyColors.neutral600,
    outline: isDark ? JobifyColors.neutral500 : JobifyColors.neutral300,
    outlineVariant: isDark ? JobifyColors.neutral700 : JobifyColors.neutral200,
  );

  final textTheme = JobifyTypography.textTheme(brightness);

  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    textTheme: textTheme,
    scaffoldBackgroundColor: scheme.surface,
    appBarTheme: AppBarTheme(
      backgroundColor: scheme.surface,
      foregroundColor: scheme.onSurface,
      centerTitle: false,
      elevation: 0,
      titleTextStyle: textTheme.titleLarge,
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        shape: const RoundedRectangleBorder(
          borderRadius: JobifyRadii.borderRadiusMd,
        ),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        textStyle: textTheme.labelLarge,
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        shape: const RoundedRectangleBorder(
          borderRadius: JobifyRadii.borderRadiusMd,
        ),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        textStyle: textTheme.labelLarge,
      ),
    ),
    cardTheme: CardThemeData(
      shape: const RoundedRectangleBorder(
        borderRadius: JobifyRadii.borderRadiusLg,
      ),
      margin: EdgeInsets.zero,
      elevation: 0,
      color: scheme.surfaceContainerHighest,
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      shape: const RoundedRectangleBorder(
        borderRadius: JobifyRadii.borderRadiusMd,
      ),
      backgroundColor: scheme.onSurface,
      contentTextStyle: textTheme.bodyMedium?.copyWith(color: scheme.surface),
    ),
  );
}
