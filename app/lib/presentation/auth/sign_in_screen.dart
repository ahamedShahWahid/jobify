import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:kpa_app/core/error/exceptions.dart';
import 'package:kpa_app/data/auth/google_web_sign_in.dart';
import 'package:kpa_app/presentation/auth/sign_in_controller.dart';
import 'package:kpa_app/presentation/theme/kpa_spacing.dart';

class SignInScreen extends ConsumerWidget {
  const SignInScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    ref.listen<AsyncValue<void>>(signInControllerProvider, (_, next) {
      next.whenOrNull(
        error: (e, _) {
          final msg = switch (e) {
            AuthException(:final slug)
                when slug == 'google_sign_in_cancelled' =>
              null,
            NetworkException _ =>
              "Couldn't reach KPA. Check your connection.",
            AuthException(:final detail) =>
              detail ?? 'Sign-in failed. Try again.',
            _ => 'Sign-in failed. Try again.',
          };
          if (msg != null) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text(msg)),
            );
          }
        },
      );
    });

    final state = ref.watch(signInControllerProvider);
    final isLoading = state.isLoading;
    final theme = Theme.of(context);

    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: KpaSpacing.xl),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text('KPA', style: theme.textTheme.displayMedium),
              const SizedBox(height: KpaSpacing.sm),
              Text(
                'Roles that match you, not the other way around.',
                style: theme.textTheme.bodyMedium,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: KpaSpacing.xxl),
              // Web authenticates via Google's rendered button (the only web
              // path that yields an ID token); mobile uses the imperative flow.
              if (kIsWeb)
                _WebSignInButton(isLoading: isLoading)
              else
                FilledButton.icon(
                  icon: isLoading
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child:
                              CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.login),
                  label: Text(
                      isLoading ? 'Signing in…' : 'Continue with Google'),
                  onPressed: isLoading
                      ? null
                      : () => ref
                          .read(signInControllerProvider.notifier)
                          .signInWithGoogle(),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Web sign-in affordance: shows Google's rendered button once the GIS client
/// is initialized, a spinner while initializing or while the backend exchange
/// is in flight, and a fallback message if init failed.
class _WebSignInButton extends ConsumerWidget {
  const _WebSignInButton({required this.isLoading});

  final bool isLoading;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (isLoading) {
      return const SizedBox(
        width: 24,
        height: 24,
        child: CircularProgressIndicator(strokeWidth: 2),
      );
    }
    return ref.watch(googleWebSignInProvider).when(
          data: (google) => google.button(),
          loading: () => const SizedBox(
            width: 24,
            height: 24,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
          error: (_, __) => Text(
            "Couldn't load Google sign-in. Refresh and try again.",
            style: Theme.of(context).textTheme.bodyMedium,
            textAlign: TextAlign.center,
          ),
        );
  }
}
