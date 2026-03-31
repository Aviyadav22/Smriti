import { useState } from "react";
import { DndContext, closestCenter, type DragEndEvent, TouchSensor, MouseSensor, KeyboardSensor, useSensors, useSensor } from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy, useSortable, arrayMove } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

interface Props {
  question: string;
  items: string[];            // correct order
  onComplete: (correct: boolean) => void;
}

function SortableItem({ id }: { id: string }) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id });
  const style = { transform: CSS.Transform.toString(transform), transition };

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className="border border-[#1E1E1E]/50 bg-[#111111]/80 px-4 py-3 text-sm text-[#E8E8E8] cursor-grab active:cursor-grabbing hover:border-[#C5A880]/30 transition-colors select-none touch-none min-w-0"
    >
      <span className="text-[#6B6B6B] mr-3">⠿</span>
      {id}
    </div>
  );
}

export function DragOrder({ question, items, onComplete }: Props) {
  const [order, setOrder] = useState(() => [...items].sort(() => Math.random() - 0.5));
  const [submitted, setSubmitted] = useState(false);
  const [correct, setCorrect] = useState(false);

  const sensors = useSensors(
    useSensor(MouseSensor),
    useSensor(TouchSensor),
    useSensor(KeyboardSensor),
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      setOrder((prev) => {
        const oldIndex = prev.indexOf(active.id as string);
        const newIndex = prev.indexOf(over.id as string);
        return arrayMove(prev, oldIndex, newIndex);
      });
    }
  };

  const handleSubmit = () => {
    const isCorrect = order.every((item, i) => item === items[i]);
    setCorrect(isCorrect);
    setSubmitted(true);
    onComplete(isCorrect);
  };

  return (
    <div className="max-w-lg mx-auto">
      <p className="text-base text-[#E8E8E8] mb-6">{question}</p>
      {!submitted ? (
        <>
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
            <SortableContext items={order} strategy={verticalListSortingStrategy}>
              <div className="space-y-2 mb-6">
                {order.map((item) => (
                  <SortableItem key={item} id={item} />
                ))}
              </div>
            </SortableContext>
          </DndContext>
          <button
            onClick={handleSubmit}
            className="w-full border border-[#C5A880]/40 text-[#C5A880] py-2.5 text-sm font-mono uppercase tracking-wider hover:bg-[#C5A880]/10 transition-colors"
          >
            Check Order
          </button>
        </>
      ) : (
        <div className={`text-center py-4 text-lg font-mono ${correct ? "text-[#4ADE80]" : "text-[#EF4444]"}`}>
          {correct ? "✓ Perfect order!" : "✗ Not quite right. The correct order has been noted."}
        </div>
      )}
    </div>
  );
}
