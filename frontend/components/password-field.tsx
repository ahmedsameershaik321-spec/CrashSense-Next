"use client";

import { useState, type ComponentProps } from "react";
import { Eye, EyeOff } from "lucide-react";
import { FormField } from "@/components/form-field";

type PasswordFieldProps = Omit<ComponentProps<typeof FormField>, "type">;

export function PasswordField(props: PasswordFieldProps) {
  const [visible, setVisible] = useState(false);

  return (
    <div className="relative">
      <FormField {...props} className="pr-12" type={visible ? "text" : "password"} />
      <button
        aria-label={visible ? `Hide ${props.label.toLowerCase()}` : `Show ${props.label.toLowerCase()}`}
        aria-pressed={visible}
        className="absolute bottom-2.5 right-2 inline-flex h-9 w-9 items-center justify-center rounded-md text-slate-500 transition hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        onClick={() => setVisible((current) => !current)}
        type="button"
      >
        {visible ? (
          <EyeOff aria-hidden="true" className="h-4 w-4" />
        ) : (
          <Eye aria-hidden="true" className="h-4 w-4" />
        )}
      </button>
    </div>
  );
}
