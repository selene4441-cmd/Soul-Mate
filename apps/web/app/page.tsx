"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { ApiError, postJson } from "@/lib/api";

const loginSchema = z.object({
  email: z.string().email("请输入有效邮箱"),
  password: z.string().min(10, "密码至少 10 位"),
});

const registerSchema = loginSchema.extend({
  display_name: z.string().min(1, "请填写称呼").max(80),
  birth_year: z.number().int().min(1900).max(2010),
  region: z.string().min(1, "请填写常驻地区").max(80),
});

type LoginValues = z.infer<typeof loginSchema>;
type RegisterValues = z.infer<typeof registerSchema>;

type SessionResponse = { user: { id: string }; csrf_token: string };

export default function LandingPage() {
  const [mode, setMode] = useState<"login" | "register">("register");
  const [serverError, setServerError] = useState("");
  const router = useRouter();

  const loginForm = useForm<LoginValues>({ resolver: zodResolver(loginSchema) });
  const registerForm = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { birth_year: 1994 },
  });

  async function login(values: LoginValues) {
    setServerError("");
    try {
      await postJson<SessionResponse>("/auth/login", values);
      router.push("/home");
    } catch (error) {
      setServerError(error instanceof ApiError ? error.message : "登录未完成，请稍后重试。");
    }
  }

  async function register(values: RegisterValues) {
    setServerError("");
    try {
      await postJson<SessionResponse>("/auth/register", values);
      router.push("/onboarding");
    } catch (error) {
      setServerError(error instanceof ApiError ? error.message : "注册未完成，请稍后重试。");
    }
  }

  return (
    <div className="min-h-screen">
      <header className="shell flex min-h-20 items-center justify-between">
        <div className="flex items-center gap-3 font-semibold">
          <span className="grid h-10 w-10 place-items-center rounded-full bg-[var(--moss)] text-white">同</span>
          同频
        </div>
        <span className="chip">v0.1 冷启动</span>
      </header>

      <main className="shell grid items-center gap-12 pb-20 pt-8 lg:grid-cols-[1.25fr_0.75fr] lg:pt-20">
        <section>
          <p className="eyebrow mb-5">关系信号 · 持续确认</p>
          <h1 className="display max-w-3xl">
            先看见彼此的
            <span className="text-[var(--moss)]">相处线索</span>
            ，再决定是否继续了解。
          </h1>
          <p className="muted mt-7 max-w-2xl text-lg leading-8">
            同频不替关系下结论。我们把共同点、差异和仍然未知的部分放在一起，
            让你用具体交谈继续确认。
          </p>
          <div className="mt-9 grid gap-3 sm:grid-cols-3">
            {[
              ["可追溯", "每条线索来自你的主动填写"],
              ["可修正", "像与不像都可以反馈"],
              ["安全优先", "边界与硬约束可以否决推荐"],
            ].map(([title, text]) => (
              <div key={title} className="rounded-3xl border border-[var(--line)] bg-white/60 p-4">
                <strong>{title}</strong>
                <p className="muted mt-1 text-sm leading-6">{text}</p>
              </div>
            ))}
          </div>
          <div className="muted mt-7 flex flex-wrap gap-x-6 gap-y-2 text-sm">
            <Link href="/privacy" className="underline underline-offset-4">查看数据处理原则</Link>
            <span>不展示关系结果的确定性数字</span>
            <span>不使用未经授权的第三方聊天</span>
          </div>
        </section>

        <section className="panel" aria-labelledby="auth-title">
          <div className="mb-6 grid grid-cols-2 rounded-full bg-[#ece9df] p-1">
            <button
              type="button"
              className={`rounded-full px-4 py-2 ${mode === "register" ? "bg-white font-semibold shadow-sm" : "muted"}`}
              onClick={() => setMode("register")}
            >
              开始使用
            </button>
            <button
              type="button"
              className={`rounded-full px-4 py-2 ${mode === "login" ? "bg-white font-semibold shadow-sm" : "muted"}`}
              onClick={() => setMode("login")}
            >
              已有账号
            </button>
          </div>
          <h2 id="auth-title" className="text-2xl font-semibold">
            {mode === "register" ? "建立你的关系信号" : "继续上次的确认"}
          </h2>
          <p className="muted mt-2 text-sm leading-6">
            注册后先阅读并选择授权范围，再开始场景取舍题。
          </p>

          {mode === "register" ? (
            <form className="mt-6 space-y-4" onSubmit={registerForm.handleSubmit(register)}>
              <label className="block text-sm font-medium">
                你的称呼
                <input className="field mt-2" {...registerForm.register("display_name")} />
                <span className="mt-1 block text-xs text-[var(--clay)]">
                  {registerForm.formState.errors.display_name?.message}
                </span>
              </label>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="block text-sm font-medium">
                  出生年份
                  <input className="field mt-2" type="number" {...registerForm.register("birth_year", { valueAsNumber: true })} />
                  <span className="mt-1 block text-xs text-[var(--clay)]">
                    {registerForm.formState.errors.birth_year?.message}
                  </span>
                </label>
                <label className="block text-sm font-medium">
                  常驻地区
                  <input className="field mt-2" placeholder="例如 上海" {...registerForm.register("region")} />
                  <span className="mt-1 block text-xs text-[var(--clay)]">
                    {registerForm.formState.errors.region?.message}
                  </span>
                </label>
              </div>
              <label className="block text-sm font-medium">
                邮箱
                <input className="field mt-2" type="email" autoComplete="email" {...registerForm.register("email")} />
                <span className="mt-1 block text-xs text-[var(--clay)]">
                  {registerForm.formState.errors.email?.message}
                </span>
              </label>
              <label className="block text-sm font-medium">
                密码
                <input
                  className="field mt-2"
                  type="password"
                  autoComplete="new-password"
                  {...registerForm.register("password")}
                />
                <span className="mt-1 block text-xs text-[var(--clay)]">
                  {registerForm.formState.errors.password?.message}
                </span>
              </label>
              <button className="button-primary w-full" disabled={registerForm.formState.isSubmitting}>
                {registerForm.formState.isSubmitting ? "正在建立…" : "继续授权与问卷"}
              </button>
            </form>
          ) : (
            <form className="mt-6 space-y-4" onSubmit={loginForm.handleSubmit(login)}>
              <label className="block text-sm font-medium">
                邮箱
                <input className="field mt-2" type="email" autoComplete="email" {...loginForm.register("email")} />
                <span className="mt-1 block text-xs text-[var(--clay)]">
                  {loginForm.formState.errors.email?.message}
                </span>
              </label>
              <label className="block text-sm font-medium">
                密码
                <input
                  className="field mt-2"
                  type="password"
                  autoComplete="current-password"
                  {...loginForm.register("password")}
                />
                <span className="mt-1 block text-xs text-[var(--clay)]">
                  {loginForm.formState.errors.password?.message}
                </span>
              </label>
              <button className="button-primary w-full" disabled={loginForm.formState.isSubmitting}>
                {loginForm.formState.isSubmitting ? "正在确认…" : "进入同频"}
              </button>
            </form>
          )}
          {serverError ? <p className="mt-4 text-sm text-[var(--clay)]">{serverError}</p> : null}
        </section>
      </main>
    </div>
  );
}
