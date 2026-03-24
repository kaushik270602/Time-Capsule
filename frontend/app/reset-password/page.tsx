"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import PasswordResetForm from "@/components/auth/PasswordResetForm";
import AuthLayout from "@/components/auth/AuthLayout";

function ResetPasswordContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") || undefined;

  if (!token) {
    return (
      <div className="text-center p-6">
        <p className="text-red-600">Invalid or missing reset token.</p>
        <a href="/forgot-password" className="text-indigo-600 hover:text-indigo-500 font-medium mt-2 inline-block">
          Request a new reset link
        </a>
      </div>
    );
  }

  return <PasswordResetForm token={token} />;
}

export default function ResetPasswordPage() {
  return (
    <AuthLayout>
      <Suspense fallback={<div className="text-center p-6">Loading...</div>}>
        <ResetPasswordContent />
      </Suspense>
    </AuthLayout>
  );
}
