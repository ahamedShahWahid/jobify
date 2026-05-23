import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:kpa_app/app.dart';
import 'package:kpa_app/core/config/env.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  Env.validateOrThrow();
  runApp(const ProviderScope(child: KpaApp()));
}
