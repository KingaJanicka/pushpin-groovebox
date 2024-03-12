import * as glob from "glob";
import { validate } from "jsonschema";
import { cwd } from "node:process";
import path from "node:path";
import { readFileSync, write, writeFileSync } from "node:fs";

const schemas = glob
  .sync(path.resolve(path.join(cwd(), "..", "docs", "schemas", "v2", "*.json")))
  .reduce(
    (a, c) => ({
      ...a,
      [path.basename(c, ".json")]: JSON.parse(readFileSync(c, "utf-8")),
    }),
    {}
  );

const old_devices = glob
  .sync(path.resolve(path.join(cwd(), "..", "device_definitions", "*.json")))
  .map((path) => [path, JSON.parse(readFileSync(path, "utf-8"))]);

const convert_message = (arr) => ({
  $type: "message",
  $comment: arr.length === 3 ? arr[0] : "",
  address: arr.length === 3 ? arr[1] : arr[0],
  value: arr.length === 3 ? arr[2] : arr[1],
});

const is_menu = (item) =>
  (item.controls &&
    item.controls.every((d) => Array.isArray(d) && d.length === 3)) ||
  (Array.isArray(item) && item.length === 3);

const is_range_control = (item) => Array.isArray(item) && d.length === 4;

const is_group = (item) =>
  item.controls &&
  (item.controls.every((d) => Array.isArray(d) && d.length === 4) ||
    item.controls.every((d) => is_menu(item) || is_range_control(item)));

const convert_menu_item = (item) => ({
  $type: "menu-item",
  label: item[0],
  onselect: convert_message(item),
});

const convert_menu_or_group = (item) => {
  if (is_menu(item)) {
    return {
      $type: "control-menu",
      items: item.controls.map((item) => convert_menu_item(item)),
    };
  } else if (is_group(item)) {
    return {
      $type: "group",
      label: item.name,
      value: item.value ? convert_message(item.value) : undefined,
      controls: item.controls.map((item) => convert_control(item)),
    };
  } else {
    return {
      $type: "group",
      label: item.name,
      value: item.value ? convert_message(item.value) : undefined,
      groups: item.controls.map((item) => convert_menu_or_group(item)),
    };
  }
};

const convert_switch_menu_or_group = (item) => {
  if (item.controls && item.controls.every((d) => is_group(d) || is_menu(d))) {
    return convert_menu_or_group(item);
  }
  return {
    $type: "control-switch",
    groups: item.controls.map((item) => convert_menu_or_group(item)),
  };
};

const convert_control = (arr) => {
  if (Array.isArray(arr)) {
    switch (arr.length) {
      case 0:
        return {
          $type: "control-spacer",
        };
      case 2:
        const [macroLabel, macroParams] = arr;
        return {
          $type: "control-macro",
          label: macroLabel,
          params: macroParams.map((mp) => convert_control(mp)),
        };
      case 4:
        const [label, address, min, max] = arr;
        return {
          $type: "control-range",
          label,
          address,
          min,
          max,
        };
    }
  }

  return convert_switch_menu_or_group(arr);
};

const new_devices = old_devices.map(([p, d]) => {
  const newD = {
    name: d.device_name,
    slot: d.device_slots.length ? d.device_slots[0] : null,
    init: d.init.map((init) => convert_message(init)),
    controls: d.osc.controls.map((c) => convert_control(c)),
  };

  return [p, newD];
});

new_devices.forEach(([p, d]) => {
  writeFileSync(p, JSON.stringify(d, null, "\t"));
});
