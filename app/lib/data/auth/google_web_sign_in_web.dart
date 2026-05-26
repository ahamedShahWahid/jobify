import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:google_sign_in_web/web_only.dart' as web;

import 'package:kpa_app/core/config/env.dart';
import 'package:kpa_app/data/auth/google_web_sign_in.dart';

/// Web implementation, selected only when `dart.library.js_interop` is present.
GoogleWebSignIn createGoogleWebSignIn() => _WebGoogleSignIn();

class _WebGoogleSignIn implements GoogleWebSignIn {
  _WebGoogleSignIn()
      : _sdk = GoogleSignIn(
          // Web uses `clientId` (NOT `serverClientId`, which asserts on web).
          // The returned credential's `aud` is this web client id, which is
          // what the backend's KPA_GOOGLE_OAUTH_CLIENT_IDS verifies against.
          clientId: Env.googleWebClientId,
          scopes: const ['email', 'profile', 'openid'],
        );

  final GoogleSignIn _sdk;
  final StreamController<String> _tokens = StreamController<String>.broadcast();
  StreamSubscription<GoogleSignInAccount?>? _sub;

  @override
  Future<void> initialize() async {
    _sub ??= _sdk.onCurrentUserChanged.listen((account) async {
      if (account == null) return;
      final auth = await account.authentication;
      final idToken = auth.idToken;
      if (idToken != null) _tokens.add(idToken);
    });
    // signInSilently triggers the GIS client `init`, which `renderButton()`
    // requires. Returns null when there's no existing session — that's fine,
    // interactive sign-in happens through the rendered button.
    try {
      await _sdk.signInSilently();
    } catch (_) {
      // No prior session / silent sign-in unavailable — expected.
    }
  }

  @override
  Stream<String> get idTokens => _tokens.stream;

  @override
  Widget button() => web.renderButton();

  @override
  void dispose() {
    _sub?.cancel();
    _tokens.close();
  }
}
