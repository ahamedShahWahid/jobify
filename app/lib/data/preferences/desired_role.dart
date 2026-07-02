import 'package:json_annotation/json_annotation.dart';

/// Mirrors the backend RoleCategory StrEnum (core/src/jobify/db/models.py).
/// `unknown` is the forward-compat sentinel for an unrecognised wire value.
enum DesiredRole {
  @JsonValue('software_engineering')
  softwareEngineering,
  @JsonValue('data_analytics')
  dataAnalytics,
  @JsonValue('product_management')
  productManagement,
  @JsonValue('design')
  design,
  @JsonValue('sales')
  sales,
  @JsonValue('marketing')
  marketing,
  @JsonValue('customer_support')
  customerSupport,
  @JsonValue('operations')
  operations,
  @JsonValue('finance_accounting')
  financeAccounting,
  @JsonValue('hr_recruiting')
  hrRecruiting,
  @JsonValue('legal')
  legal,
  @JsonValue('consulting')
  consulting,
  @JsonValue('business_development')
  businessDevelopment,
  @JsonValue('content_communications')
  contentCommunications,
  @JsonValue('administration')
  administration,
  @JsonValue('other')
  other,
  unknown,
}

extension DesiredRoleLabel on DesiredRole {
  /// Display label for the dropdown. `unknown` should never reach the UI
  /// (the form only ever sends a real value or null), but a label avoids a
  /// crash if it somehow does.
  String get label => switch (this) {
        DesiredRole.softwareEngineering => 'Software Engineering',
        DesiredRole.dataAnalytics => 'Data & Analytics',
        DesiredRole.productManagement => 'Product Management',
        DesiredRole.design => 'Design',
        DesiredRole.sales => 'Sales',
        DesiredRole.marketing => 'Marketing',
        DesiredRole.customerSupport => 'Customer Support',
        DesiredRole.operations => 'Operations',
        DesiredRole.financeAccounting => 'Finance & Accounting',
        DesiredRole.hrRecruiting => 'HR & Recruiting',
        DesiredRole.legal => 'Legal',
        DesiredRole.consulting => 'Consulting',
        DesiredRole.businessDevelopment => 'Business Development',
        DesiredRole.contentCommunications => 'Content & Communications',
        DesiredRole.administration => 'Administration',
        DesiredRole.other => 'Other',
        DesiredRole.unknown => 'Unknown',
      };
}

extension DesiredRoleWireValue on DesiredRole {
  /// The wire value sent to the backend, mirroring each @JsonValue above.
  /// Hand-written (not code-generated) because PreferencesUpdateDto's
  /// toJson() is hand-written too — see that file for why.
  String? get wireValue => switch (this) {
        DesiredRole.softwareEngineering => 'software_engineering',
        DesiredRole.dataAnalytics => 'data_analytics',
        DesiredRole.productManagement => 'product_management',
        DesiredRole.design => 'design',
        DesiredRole.sales => 'sales',
        DesiredRole.marketing => 'marketing',
        DesiredRole.customerSupport => 'customer_support',
        DesiredRole.operations => 'operations',
        DesiredRole.financeAccounting => 'finance_accounting',
        DesiredRole.hrRecruiting => 'hr_recruiting',
        DesiredRole.legal => 'legal',
        DesiredRole.consulting => 'consulting',
        DesiredRole.businessDevelopment => 'business_development',
        DesiredRole.contentCommunications => 'content_communications',
        DesiredRole.administration => 'administration',
        DesiredRole.other => 'other',
        DesiredRole.unknown => null,
      };
}
