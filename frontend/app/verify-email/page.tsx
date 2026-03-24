"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { authApi } from "@/lib/api";
import AuthLayout from "@/components/auth/AuthLayout";

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setMessage("Missing verification token.");
      return;
    }
    authApi
      .verifyEmail(token)
      .then(() => {
        setStatus("success");
        setMessage("Your email has been verified successfully.");
      })
      .catch((err) => {
        setStatus("error");
        setMessage(err.response?.data?.detail || "Verification failed. The link may have expired.");
      });
  }, [token]);

  return (
    <div className="text-center p-6">
      {status === "loading" && (
        <p className="text-gray-600">Verifying your email...</p>
      )}
      {status === "success" && (
        <>
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-green-100">
            <svg className="h-6 w-6 text-green-600" fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Email verified</h2>
          <p className="text-gray-600 mb-4">{message}</p>
          <Link href="/login" className="text-indigo-600 hover:text-indigo-500 font-medium">
            Sign in to your account
          </Link>
        </>
      )}
      {status === "error" && (
        <>
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-red-100">
            <svg className="h-6 w-6 text-red-600" fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Verification failed</h2>
          <p className="text-gray-600 mb-4">{message}</p>
          <Link href="/register" className="text-indigo-600 hover:text-indigo-500 font-medium">
            Try registering again
          </Link>
        </>
      )}
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <AuthLayout>
      <Suspense fallback={<div className="text-center p-6">Loading...</div>}>
        <VerifyEmailContent />
      </Suspense>
    </AuthLayout>
  );
}
