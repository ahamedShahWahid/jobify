import 'dart:developer' as developer;

import 'package:jobify_app/core/config/env.dart';

/// Minimal logger. Replace the implementation with a real telemetry
/// adapter (Sentry / Crashlytics / Fluent Bit forwarder) when that
/// lands.
///
/// Semantics:
/// - In dev builds, every level prints via dart:developer.log (shows in
///   IDE).
/// - In prod builds, info/debug are silent; warn/error still print so
///   they show up in platform-specific crash logs.
class JobifyLogger {
  JobifyLogger(this._name);

  factory JobifyLogger.named(String name) => JobifyLogger(name);

  final String _name;

  void debug(String message, {Object? error, StackTrace? stack}) {
    if (!Env.isDev) return;
    developer.log(
      message,
      name: _name,
      level: 500,
      error: error,
      stackTrace: stack,
    );
  }

  void info(String message, {Object? error, StackTrace? stack}) {
    if (!Env.isDev) return;
    developer.log(
      message,
      name: _name,
      level: 800,
      error: error,
      stackTrace: stack,
    );
  }

  void warn(String message, {Object? error, StackTrace? stack}) {
    developer.log(
      message,
      name: _name,
      level: 900,
      error: error,
      stackTrace: stack,
    );
  }

  void error(String message, {Object? error, StackTrace? stack}) {
    developer.log(
      message,
      name: _name,
      level: 1000,
      error: error,
      stackTrace: stack,
    );
  }
}
