import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:kpa_app/presentation/routing/router.dart';
import 'package:kpa_app/presentation/theme/build_theme.dart';

class KpaApp extends ConsumerWidget {
  const KpaApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);
    return MaterialApp.router(
      title: 'KPA',
      theme: buildTheme(Brightness.light),
      // Dark plumbed but disabled per spec:
      // darkTheme: buildTheme(Brightness.dark),
      themeMode: ThemeMode.light,
      routerConfig: router,
      debugShowCheckedModeBanner: false,
    );
  }
}
