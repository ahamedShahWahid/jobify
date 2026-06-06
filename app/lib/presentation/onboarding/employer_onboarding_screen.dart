import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:kpa_app/core/error/exceptions.dart';
import 'package:kpa_app/presentation/onboarding/employer_onboarding_controller.dart';

class EmployerOnboardingScreen extends ConsumerStatefulWidget {
  const EmployerOnboardingScreen({super.key});

  @override
  ConsumerState<EmployerOnboardingScreen> createState() =>
      _EmployerOnboardingScreenState();
}

class _EmployerOnboardingScreenState
    extends ConsumerState<EmployerOnboardingScreen> {
  final _formKey = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _gst = TextEditingController();

  @override
  void dispose() {
    _name.dispose();
    _gst.dispose();
    super.dispose();
  }

  String? _validateName(String? v) {
    final s = (v ?? '').trim();
    if (s.length < 2) return 'Enter your company name (min 2 characters)';
    if (s.length > 200) return 'Company name is too long';
    return null;
  }

  String? _validateGst(String? v) {
    final s = (v ?? '').trim();
    if (s.isEmpty) return null;
    if (s.length != 15) return 'GSTIN must be exactly 15 characters';
    return null;
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    await ref.read(employerOnboardingControllerProvider.notifier).submit(
          name: _name.text.trim(),
          gst: _gst.text.trim().isEmpty ? null : _gst.text.trim(),
        );
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(employerOnboardingControllerProvider);
    final isLoading = state.isLoading;

    ref.listen(employerOnboardingControllerProvider, (_, next) {
      if (next.hasError && context.mounted) {
        final err = next.error;
        final msg = err is ApiException && err.slug == 'employer_name_taken'
            ? 'That company name is already registered.'
            : 'Could not create employer. Please try again.';
        ScaffoldMessenger.of(context)
          ..hideCurrentSnackBar()
          ..showSnackBar(SnackBar(content: Text(msg)));
      }
    });

    return Scaffold(
      appBar: AppBar(title: const Text('Set up your company')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text('Tell us about your company to start posting jobs.'),
              const SizedBox(height: 16),
              TextFormField(
                controller: _name,
                decoration: const InputDecoration(
                  labelText: 'Company name',
                  border: OutlineInputBorder(),
                ),
                validator: _validateName,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _gst,
                decoration: const InputDecoration(
                  labelText: 'GSTIN (optional)',
                  border: OutlineInputBorder(),
                ),
                validator: _validateGst,
              ),
              const SizedBox(height: 24),
              FilledButton(
                onPressed: isLoading ? null : _submit,
                child: isLoading
                    ? const SizedBox(
                        height: 18,
                        width: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('Create company'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
