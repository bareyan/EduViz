export interface StepProps {
  number: number;
  title: string;
  description: string;
}

export function Step({ number, title, description }: StepProps) {
  return (
    <div className="relative">
      <div className="flex items-center gap-4 mb-3">
        <div className="w-10 h-10 rounded-full bg-math-blue/20 flex items-center justify-center text-math-blue font-bold">
          {number}
        </div>
        {number < 4 && (
          <div className="hidden md:block flex-1 h-0.5 bg-gradient-to-r from-math-blue/50 to-transparent" />
        )}
      </div>
      <h3 className="font-semibold mb-1">{title}</h3>
      <p className="text-sm text-gray-500">{description}</p>
    </div>
  );
}
