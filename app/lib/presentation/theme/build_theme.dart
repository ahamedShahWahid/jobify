import 'package:flutter/material.dart';

import 'package:kpa_app/presentation/theme/kpa_colors.dart';
import 'package:kpa_app/presentation/theme/kpa_radii.dart';
import 'package:kpa_app/presentation/theme/kpa_typography.dart';

/// Single ThemeData factory for both brightness modes. v0 only ever calls
/// this with [Brightness.light]; the dark branch is plumbed so flipping
/// `themeMode` later is a one-line change.
ThemeData buildTheme(Brightness brightness) {
  final isDark = brightness == Brightness.dark;
  final scheme = ColorScheme(
    brightness: brightness,
    primary: KpaColors.indigo500,
    onPrimary: KpaColors.neutral0,
    primaryContainer: isDark ? KpaColors.indigo700 : KpaColors.indigo100,
    onPrimaryContainer: isDark ? KpaColors.indigo100 : KpaColors.indigo900,
    secondary: KpaColors.indigo400,
    onSecondary: KpaColors.neutral0,
    secondaryContainer: isDark ? KpaColors.indigo800 : KpaColors.indigo50,
    onSecondaryContainer: isDark ? KpaColors.indigo50 : KpaColors.indigo800,
    error: KpaColors.error,
    onError: KpaColors.onError,
    surface: isDark ? KpaColors.neutral900 : KpaColors.neutral0,
    onSurface: isDark ? KpaColors.neutral50 : KpaColors.neutral900,
    surfaceContainerHighest:
        isDark ? KpaColors.neutral800 : KpaColors.neutral50,
    onSurfaceVariant: isDark ? KpaColors.neutral300 : KpaColors.neutral600,
    outline: isDark ? KpaColors.neutral500 : KpaColors.neutral300,
    outlineVariant: isDark ? KpaColors.neutral700 : KpaColors.neutral200,
  );

  final textTheme = KpaTypography.textTheme(brightness);

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
          borderRadius: KpaRadii.borderRadiusMd,
        ),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        textStyle: textTheme.labelLarge,
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        shape: const RoundedRectangleBorder(
          borderRadius: KpaRadii.borderRadiusMd,
        ),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        textStyle: textTheme.labelLarge,
      ),
    ),
    cardTheme: CardThemeData(
      shape: const RoundedRectangleBorder(
        borderRadius: KpaRadii.borderRadiusLg,
      ),
      margin: EdgeInsets.zero,
      elevation: 0,
      color: scheme.surfaceContainerHighest,
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      shape: const RoundedRectangleBorder(
        borderRadius: KpaRadii.borderRadiusMd,
      ),
      backgroundColor: scheme.onSurface,
      contentTextStyle: textTheme.bodyMedium?.copyWith(color: scheme.surface),
    ),
  );
}
