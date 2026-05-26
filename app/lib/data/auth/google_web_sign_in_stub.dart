import 'package:flutter/widgets.dart';

import 'package:kpa_app/data/auth/google_web_sign_in.dart';

/// Selected on every non-web build. Never invoked at runtime — the sign-in
/// screen only reaches the web helper behind a `kIsWeb` guard — but it must
/// exist so `google_web_sign_in.dart` compiles off the web.
GoogleWebSignIn createGoogleWebSignIn() => _StubGoogleWebSignIn();

class _StubGoogleWebSignIn implements GoogleWebSignIn {
  @override
  Future<void> initialize() async {}

  @override
  Stream<String> get idTokens => const Stream.empty();

  @override
  Widget button() => const SizedBox.shrink();

  @override
  void dispose() {}
}
