import 'dart:io' show HttpOverrides;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/presentation/theme/build_theme.dart';
import 'package:kpa_app/presentation/theme/kpa_colors.dart';

void main() {
  setUpAll(() {
    // Initialize Flutter bindings and permit HTTP for google_fonts.
    WidgetsFlutterBinding.ensureInitialized();
    HttpOverrides.global = _TestHttpOverrides();
  });

  group('buildTheme', () {
    test('light theme has expected brightness + surface color', () {
      final theme = buildTheme(Brightness.light);
      expect(theme.brightness, Brightness.light);
      expect(theme.colorScheme.surface, KpaColors.neutral0);
      expect(theme.colorScheme.primary, KpaColors.indigo500);
    });

    test('dark theme has expected brightness + inverted surface', () {
      final theme = buildTheme(Brightness.dark);
      expect(theme.brightness, Brightness.dark);
      expect(theme.colorScheme.surface, KpaColors.neutral900);
    });

    test('uses material 3', () {
      expect(buildTheme(Brightness.light).useMaterial3, isTrue);
    });

    test('light theme has expected color scheme slots', () {
      final theme = buildTheme(Brightness.light);
      expect(theme.colorScheme.onPrimary, KpaColors.neutral0);
      expect(theme.colorScheme.error, KpaColors.error);
      expect(theme.colorScheme.onError, KpaColors.onError);
    });

    test('text theme is non-null and has bodyLarge configured', () {
      final theme = buildTheme(Brightness.light);
      expect(theme.textTheme.bodyLarge, isNotNull);
      expect(theme.textTheme.bodyLarge?.fontSize, 16);
      expect(theme.textTheme.headlineMedium, isNotNull);
      expect(theme.textTheme.labelLarge, isNotNull);
    });
  });
}

/// Permit HTTP requests for google_fonts font fetching in tests.
/// Using HttpOverrides() directly without subclassing (minimal override).
class _TestHttpOverrides extends HttpOverrides {}
